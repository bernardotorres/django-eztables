# -*- coding: utf-8 -*-
import json
import re

from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.generic import View
from django.views.generic.list import MultipleObjectMixin

from eztables.forms import DatatablesForm, DESC


JSON_MIMETYPE = 'application/json'

RE_FORMATTED = re.compile(r'\{(\w+)\}')


class DatatablesView(MultipleObjectMixin, View):
    '''
    Render a paginated server-side Datatables JSON view.

    See: http://www.datatables.net/usage/server-side
    '''
    fields = []
    _fields = None

    def post(self, request, *args, **kwargs):
        return self.process_response(request.POST)

    def get(self, request, *args, **kwargs):
        return self.process_response(request.GET)

    def process_response(self, data):
        self.form = DatatablesForm(data)
        if self.form.is_valid():
            self.object_list = self.get_queryset().values(*self.get_fields())
            return self.render_to_response(self.form)
        else:
            return HttpResponseBadRequest()

    def get_fields(self):
        if not self._fields:
            self._fields = []
            for field in self.fields:
                if RE_FORMATTED.match(field):
                    self._fields.extend(RE_FORMATTED.findall(field))
                else:
                    self._fields.append(field)
        return self._fields

    def get_orders(self):
        '''Get ordering fields for ``QuerySet.order_by``'''
        iSortingCols = self.form.cleaned_data['iSortingCols']
        orders_idx = [self.form.cleaned_data['iSortCol_%s' % i] for i in xrange(iSortingCols)]
        orders_dirs = [self.form.cleaned_data['sSortDir_%s' % i] for i in xrange(iSortingCols)]
        orders = []
        for idx, field_idx in enumerate(orders_idx):
            field, direction = self.fields[field_idx], orders_dirs[idx]
            direction = '-' if direction == DESC else ''
            if RE_FORMATTED.match(field):
                tokens = RE_FORMATTED.findall(field)
                orders.extend(['%s%s' % (direction, token) for token in tokens])
            else:
                orders.append('%s%s' % (direction, field))
        return orders

    def get_queryset(self):
        '''Apply Datatables sort and search criterion to QuerySet'''
        qs = super(DatatablesView, self).get_queryset()
        return qs.order_by(*self.get_orders())

    def get_page(self, form):
        '''Get the request page'''
        page_size = form.cleaned_data['iDisplayLength']
        start_index = form.cleaned_data['iDisplayStart']
        paginator = Paginator(self.object_list, page_size)
        num_page = (start_index / page_size) + 1
        return paginator.page(num_page)

    def get_rows(self, rows):
        '''Format all rows'''
        return [self.get_row(row) for row in rows]

    def get_row(self, row):
        '''Format a single row (if necessary)'''
        return [field.format(**row) if RE_FORMATTED.match(field) else row[field] for field in self.fields]

    def render_to_response(self, form, **kwargs):
        '''Render Datatables expected JSON format'''
        page = self.get_page(form)
        data = {
            'iTotalRecords': page.paginator.count,
            'iTotalDisplayRecords': page.paginator.count,
            'sEcho': form.cleaned_data['sEcho'],
            'aaData': self.get_rows(page.object_list),
        }
        return self.json_response(data)

    def json_response(self, data):
        return HttpResponse(
            json.dumps(data, cls=DjangoJSONEncoder),
            mimetype=JSON_MIMETYPE
        )
