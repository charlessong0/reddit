from __future__ import with_statement

from Queue import Queue
from threading import Thread
import time
from datetime import datetime, date
from time import strftime

from pylons import g, config

from r2.models import *
from r2.lib.contrib import pysolr
from r2.lib.contrib.pysolr import SolrError
from r2.lib.utils import timeago
from r2.lib.utils import unicode_safe, tup
from r2.lib.cache import SelfEmptyingCache
from r2.lib import amqp


class Field(object):
    """
       Describes a field of a Thing that is searchable by Solr. Used
       by `search_fields` below
    """
    def __init__(self, name, thing_attr_func = None, store = True,
                 tokenize=False, is_number=False, reverse=False,
                 is_date = False):
        self.name = name
        self.thing_attr_func = self.make_extractor(thing_attr_func)

    def make_extractor(self,thing_attr_func):
        if not thing_attr_func:
            return self.make_extractor(self.name)
        elif isinstance(thing_attr_func,str):
            return (lambda x: getattr(x,thing_attr_func))
        else:
            return thing_attr_func

    def extract_from(self,thing):
        return self.thing_attr_func(thing)

class ThingField(Field):
    """
        ThingField('field_name',Author,'author_id','name')
        is like:
          Field(name, lambda x: Author._byID(x.author_id,data=True).name)
        but faster because lookups are done in batch
    """
    def __init__(self,name,cls,id_attr,lu_attr_name):
        self.name = name

        self.cls          = cls         
# the class of the looked-up object
        self.id_attr      = id_attr     
# the attr of the source obj used to find the dest obj
        self.lu_attr_name = lu_attr_name 
# the attr of the dest class that we want to return

    def __str__(self):
        return ("<ThingField: (%s,%s,%s,%s)>"
                % (self.name,self.cls,self.id_attr,self.lu_attr_name))


search_fields={Thing:     (Field('fullname', '_fullname'),
                           Field('date', '_date',   is_date = True, reverse=True),
                           Field('lang'),
                           Field('ups',   '_ups',   is_number=True, reverse=True),
                           Field('downs', '_downs', is_number=True, reverse=True),
                           Field('spam','_spam'),
                           Field('deleted','_deleted'),
                           Field('hot', lambda t: t._hot*1000, is_number=True, reverse=True),
                           Field('controversy', '_controversy', is_number=True, reverse=True),
                           Field('points', lambda t: (t._ups - t._downs), is_number=True, reverse=True)),
               Subreddit: (Field('contents',
                                 lambda s: ' '.join([unicode_safe(s.name),
                                                     unicode_safe(s.title),
                                                     unicode_safe(s.description),
                                                     unicode_safe(s.firsttext)]),
                                 tokenize = True),
                           Field('boost', '_downs'),
                           #Field('title'),
                           #Field('firsttext'),
                           #Field('description'),
                           #Field('over_18'),
                           #Field('sr_type','type'),
                           ),
Link:      (Field('contents','title', tokenize = True),
                           Field('boost', lambda t: int(t._hot*1000),
                                 # yes, it's a copy of 'hot'
                                 is_number=True, reverse=True),
                           Field('author_id'),
                           ThingField('author',Account,'author_id','name'),
                           ThingField('subreddit',Subreddit,'sr_id','name'),
                           #ThingField('reddit',Subreddit,'sr_id','name'),
                           Field('sr_id'),
                           Field('url', tokenize = True),
                           #Field('domain',
                           #      lambda l: domain_permutations(domain(l.url))),
                           Field('site',
                                 lambda l: domain_permutations(domain(l.url))),
                           #Field('is_self','is_self'),
                           ),
               Comment:   (Field('contents', 'body', tokenize = True),
                           Field('boost', lambda t: int(t._hot*1000),
                                 # yes, it's a copy of 'hot'
                                 is_number=True, reverse=True),
                           ThingField('author',Account,'author_id','name'),
                           ThingField('subreddit',Subreddit,'sr_id','name'))}

