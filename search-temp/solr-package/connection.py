import things.py

class SolrConnection(object):
    """
        Represents a connection to Solr, properly limited to N
        concurrent connections. Used like

            with SolrConnection() as s:
                s.add(things)
    """
    def __init__(self,commit=False,optimize=False):
        self.commit   = commit
        self.optimize = optimize
    def __enter__(self):
        self.conn = solr_queue.get()
        return self.conn
    def __exit__(self, _type, _value, _tb):
        if self.commit:
            self.conn.commit()
        if self.optimize:
            self.conn.optimize()
        solr_queue.task_done()
        solr_queue.put(self.conn)

