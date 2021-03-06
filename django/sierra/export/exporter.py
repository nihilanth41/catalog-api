'''
Exporter module. Contains the class definition for the Exporter class,
which you can subclass to create your own Exporters to export data out
of Sierra.

Define your subclasses in a separate module and then hook it into your
project using the EXPORTER_MODULE_REGISTRY Django setting.
'''

from __future__ import unicode_literals

import logging

from django.db.models import F
from django.utils import timezone as tz
from django.conf import settings

from utils import helpers
from base import models as sierra_models
from .models import ExportInstance, ExportType, Status


class ExportError(Exception):
    pass

class Exporter(object):
    '''
    Exporter class. Subclass this to define your export jobs. Your
    class names should match exactly 1:1 with the ExportType.codes
    you've defined.
    
    Your Exporter subclasses should at the very LEAST override the
    export_records() method to define how the export works.

    If your exports are syncing Sierra with an external index or data
    store, such as Solr, then each time you load data you want to make
    sure you're also deleting records from the index that were deleted
    from Sierra (or--if you're excluding records from your external
    store based on other criteria, like record suppression, you want
    to make sure those get deleted correctly as well). In this case,
    you should override delete_records() to define how to do those
    deletions. You should also make sure you define the deletion_filter
    attribute, which provides the filter for deletions. By default, we
    get deletions from RecordMetadata--this is because, when a record
    is deleted from Sierra, all data gets removed except for the row in
    RecordMetadata. So your deletion_filter should assume you're
    filtering from the POV of the RecordMetadata model. Alternatively,
    you can simply override the get_deletions method and do whatever
    you want.
    
    The deletion_filter attribute should contain a list of
    dictionaries, where each dict contains keyword filter criteria that
    should be ANDed together and each dict group then gets ORed to
    produce the final filter.
    
    If your export job doesn't need to handle deletions, simply don't
    specify a deletion_filter in your subclass--the get_deletions
    method will return None and you won't have to worry about it.
    
    In certain cases you might want to apply some sort of base filter
    when getting records, aside from whatever export filter is used.
    For instance, if you want to filter out suppressed records. To do
    this, you can set the record_filter attribute. It uses the same
    format as deletion_filter. If you do this, make sure your deletion
    filter will select the correct records for deletion--e.g., if you
    filter out suppressed records from getting loaded into Solr, then
    you'll want to check for newly suppressed records in your deletion
    filter along with deleted records.
    
    Use select_related and prefetch_related attributes to specify what
    related objects should be prefetched or preselected when records
    are fetched from the DB. These have a MASSIVE performance benefit
    if your job uses a lot of data in related tables, so use them!
    (See the Django docs on the Queryset API for info about
    prefetch_related and select_related.)
    
    Note about max_rec_chunk and max_del_chunk. These are used by
    the tasks.py module that breaks up record loads and delegates tasks
    out to Celery. The max_rec_chunk size is the size of the chunk used
    for record loads and the max_del_chunk size is the size of chunk
    used for deletions. Depending on your export, how much
    you're loading into memory at once (e.g. with prefetch_related),
    and how many parallel chunks you're allowing, chunks greater than
    5000 could use up all your memory. Keep an eye on it when you're
    testing your export jobs, and adjust those numbers accordingly for
    your subclass.
    
    '''
    record_filter = []
    deletion_filter = []
    prefetch_related = []
    select_related = None
    max_rec_chunk = 3000
    max_del_chunk = 1000
    parallel = True
    model_name = ''

    def __init__(self, instance_pk, export_filter, export_type, options={},
                 log_label=''):
        '''
        Arguments: instance_pk is the pk for the export_instance
        attached to the export job; export_filter is the export_filter
        id string for this job; export_type is the export_type id
        string for this job; options is an optional dictionary
        containing specs for export_filter (date range, record range,
        etc.) Log_label is the label used in log messages to show the
        source of the message.
        '''
        self.instance = ExportInstance.objects.get(pk=instance_pk)
        self.status = 'unknown'
        self.export_filter = export_filter
        self.export_type = export_type
        self.options = options
        self.log_label = log_label if log_label else self.__class__.__name__
        if export_filter == 'last_export':
            try:
                latest = ExportInstance.objects.filter(
                    export_type=self.export_type, 
                    status__in=['success', 'done_with_errors']
                ).order_by(
                    '-timestamp'
                )[0]
            except IndexError:
                raise ExportError('This export type has never been run '
                                  'successfully before or does not exist. '
                                  'There is no last-updated date to use for '
                                  'this job.')
            self.options['latest_time'] = latest.timestamp
        # set up our logger for this process
        logger = logging.getLogger('exporter.file')
        self.logger = logger


    def _base_get_records(self, model_name, filters, select_related=None,
                          prefetch_related=[], fail_on_zero=False):
        '''
        Default method for getting records using self.export_filter.
        Returns the queryset. Generally you won't want to override this
        in your subclass--override get_records and get_deletions
        instead.
        
        Note that this assumes you're working with one of the main III
        record types and have the benefit of the RecordMetadata table.
        If this is not the case, you'll need to write your own
        get_records and get_deletions methods that don't use this.
        '''
        model = getattr(sierra_models, model_name)
        try:
            # do base record filter.
            records = model.objects.filter_by(self.export_filter, 
                        options=self.options)
            
            # do additional filters, if provided.
            if filters:
                q_filter = helpers.reduce_filter_kwargs(filters)
                records = records.filter(q_filter)

            # apply select_ and prefetch_related
            if select_related and select_related is not None:
                records = records.select_related(*select_related)
            if prefetch_related or prefetch_related is None:
                records = records.prefetch_related(*prefetch_related)
                
        except Exception as e:
            raise ExportError('Could not retrieve records from {} via '
                    'export filter {} using options '
                    '{}, default filter {}: {}.'
                    ''.format(model_name, self.export_filter, self.options,
                              self.record_filter, e))
        if (fail_on_zero and len(records) == 0):
            raise ExportError('0 records retrieved from {} via export '
                    'filter {} using options '
                    '{}, default filter {}.'
                    ''.format(model_name, self.export_filter, self.options, 
                                 self.filter))
        return records

    def log(self, type, message, label=''):
        '''
        Generates a log item for this export.
        Takes parameters: type and message. Type should be 'Error',
        'Warning', or 'Info'; message is the log message.
        '''
        label = label if label else self.log_label
        message = '[{}] {}'.format(label, message)
        getattr(self.logger, type.lower())(message)
        if type.lower() == 'warning' or type.lower() == 'error':
            if type.lower() == 'warning':
                self.instance.warnings = F('warnings') + 1
            else:
                self.instance.errors = F('errors') + 1
            self.instance.save()

    def save_status(self):
        '''
        Saves self.status to the database.
        '''
        try:
            status = Status.objects.get(pk=self.status)
        except Status.DoesNotExist:
            message = 'Could not set export instance status to "{}": status '\
                      'not defined in database.'.format(self.status)
            self.log('Warning', message)
            status = Status.objects.get(pk='unknown')
        self.instance.status = status
        self.instance.save()

    def get_records(self):
        '''
        Should return a full queryset or list of record objects based
        on the export filter passed into the class at initialization.
        If your export job is using one of the main III record types as
        its primary focus, then you can/should use the
        _base_get_records() method to make this simple. Otherwise 
        you'll have to override this (get_records) in your subclass.
        '''
        try:
            in_records = self._base_get_records(self.model_name, 
                            self.record_filter,
                            select_related=self.select_related,
                            prefetch_related=self.prefetch_related)
        except ExportError:
            raise
        return in_records

    def get_deletions(self):
        '''
        Like get_records, but returns a queryset of objects that
        represent things that should be deleted. If you haven't set
        self.deletion_filter, then this will just return None.
        '''
        if self.deletion_filter:
            try:
                deletions = self._base_get_records('RecordMetadata',
                                                   self.deletion_filter)
            except ExportError:
                raise
            return deletions
        else:
            return None

    def export_records(self, records, vals={}):
        '''
        Override this method in your subclasses.
        
        When passed a queryset (e.g., from self.get_records()), this
        should export the records as necessary. Totally up to you
        how to do this. Since export jobs are broken up into tasks via
        celery, and we may need to pass information from a task to a
        task or from multiple tasks to the final_callback method. Do
        this using vals. Here's how it works.
        
        If self.parallel is True, this is a job where task chunks can
        be run in parallel. In this case your export_record and
        delete_record jobs should return a dictionary of values. These
        will get passed in a list to final_callback, where you can then
        compile the info from all tasks and do something with it.
        Individual export_ and delete_ jobs won't have access to vals
        from other jobs running in parallel.
        
        If self.parallel is False, then export_record and delete_record
        job chunks will run one after the other. The vals dict will get
        passed from one chunk to the next, so each time it runs it can
        modify what's in vals. Finally, vals will be passed to
        final_callback. In this case the final_callback method will
        only have access to the vals passed to it from the last export
        or delete job chunk that ran (e.g. as a dict rather than a list
        of dicts).
        '''
        return vals

    def delete_records(self, records, vals={}):
        '''
        Override this method in your subclasses only if you need to do
        deletions.
        
        When passed a queryset (e.g., from self.get_deletions()), this
        should delete the records as necessary. Like export_records,
        you may take/return a dictionary of values to pass info from
        task to task.
        '''
        return vals

    def final_callback(self, vals={}, status='success'):
        '''
        Override this method in your subclasses if you need to provide
        something that runs once at the end of an export job that's
        been broken up into tasks.
        '''
        pass

