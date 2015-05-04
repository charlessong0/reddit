import things.py

class SearchQuery(object):
    def __init__(self, q, sort, fields = [], subreddits = [], authors = [],
                 types = [], timerange = None, spam = False, deleted = False):

        self.q = q
        self.fields = fields
        self.sort = sort
        self.subreddits = subreddits
        self.authors = authors
        self.types = types
        self.spam = spam
        self.deleted = deleted

        if timerange in ['day','month','year']:
            self.timerange = ('NOW-1%s/HOUR' % timerange.upper(),"NOW")
        elif timerange == 'week':
            self.timerange = ('NOW-7DAY/HOUR',"NOW")
        elif timerange == 'hour':
            self.timerange = ('NOW-1HOUR/MINUTE',"NOW")
        elif timerange == 'all' or timerange is None:
            self.timerange = None
        else:
            self.timerange = timerange

    def __repr__(self):
        attrs = [ "***q=%s***" % self.q ]

        if self.subreddits is not None:
            attrs.append("srs=" + '+'.join([ "%d" % s
                                             for s in self.subreddits ]))

        if self.authors is not None:
            attrs.append("authors=" + '+'.join([ "%d" % s
                                                 for s in self.authors ]))

        if self.timerange is not None:
            attrs.append("timerange=%s" % str(self.timerange))

        if self.sort is not None:
            attrs.append("sort=%r" % self.sort)
 return "<%s(%s)>" % (self.__class__.__name__, ", ".join(attrs))

    def run(self, after = None, num = 1000, reverse = False,
            _update = False):
        if not self.q:
            return pysolr.Results([],0)

        if not g.solr_url:
            raise SolrError("g.solr_url is not set")

        # there are two parts to our query: what the user typed
        # (parsed with Solr's DisMax parser), and what we are adding
        # to it. The latter is called the "boost" (and is parsed using
        # full Lucene syntax), and it can be added to via the `boost`
        # parameter
        boost = []

        if not self.spam:
            boost.append("-spam:true")
        if not self.deleted:
            boost.append("-deleted:true")

        if self.timerange:
            def time_to_searchstr(t):
                if isinstance(t, datetime):
                    t = t.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                elif isinstance(t, date):
                    t = t.strftime('%Y-%m-%dT00:00:00.000Z')
                elif isinstance(t,str):
                    t = t
                return t

            (fromtime, totime) = self.timerange
            fromtime = time_to_searchstr(fromtime)
            totime   = time_to_searchstr(totime)
            boost.append("+date:[%s TO %s]"
                         % (fromtime,totime))

        if self.subreddits:
            def subreddit_to_searchstr(sr):
                if isinstance(sr,Subreddit):
                    return ('sr_id','%d' % sr.id)
                elif isinstance(sr,str) or isinstance(sr,unicode):
                    return ('subreddit',sr)
                else:
                    return ('sr_id','%d' % sr)
s_subreddits = map(subreddit_to_searchstr, tup(self.subreddits))

            boost.append("+(%s)" % combine_searchterms(s_subreddits))

        if self.authors:
            def author_to_searchstr(a):
                if isinstance(a,Account):
                    return ('author_id','%d' % a.id)
                elif isinstance(a,str) or isinstance(a,unicode):
                    return ('author',a)
                else:
                    return ('author_id','%d' % a)

            s_authors = map(author_to_searchstr,tup(self.authors))

            boost.append('+(%s)^2' % combine_searchterms(s_authors))


        def type_to_searchstr(t):
            if isinstance(t,str):
                return ('type',t)
            else:
                return ('type',t.__name__.lower())

        s_types = map(type_to_searchstr,self.types)
        boost.append("+%s" % combine_searchterms(s_types))

        q,solr_params = self.solr_params(self.q,boost)

        search = self.run_search(q, self.sort, solr_params,
                                 reverse, after, num,
                                 _update = _update)
        return search

    @classmethod
    def run_search(cls, q, sort, solr_params, reverse, after, num,
                   _update = False):
        "returns pysolr.Results(docs=[fullname()],hits=int())"

        if reverse:
            sort = swap_strings(sort,'asc','desc')
        after = after._fullname if after else None
search = cls.run_search_cached(q, sort, 0, num, solr_params,
                                       _update = _update)
        search.docs = get_after(search.docs, after, num)

        return search

    @staticmethod
    @memoize('solr_search', solr_cache_time)
    def run_search_cached(q, sort, start, rows, other_params):
        with SolrConnection() as s:
            g.log.debug(("Searching q = %r; sort = %r,"
                         + " start = %r, rows = %r,"
                         + " params = %r")
                        % (q,sort,start,rows,other_params))

            res = s.search(q, sort, start = start, rows = rows,
                           other_params = other_params)

        # extract out the fullname in the 'docs' field, since that's
        # all we care about
        res = pysolr.Results(docs = [ i['fullname'] for i in res.docs ],
                             hits = res.hits)

        return res

    def solr_params(self,*k,**kw):
        raise NotImplementedError
