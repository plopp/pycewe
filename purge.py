#!/usr/bin/env python
# -*- coding: utf-8 -*-

import couchdb
import time

couch = None
db = None

def setup_couchdb(credentials):
   global couch
   global db
   couch = couchdb.Server("https://%(domain)s" % credentials)
   couch.resource.credentials = ('%(user)s' % credentials,"%(passw)s" % credentials)
   db = couch['%(db)s' % credentials] # existing

def main():

    #There is got to be a text file named ".credentials" in the same folder as the
    #python script, containg: <user>,<passw>,<domain>,<repldb_name>,<dbname>
    #example: user1,password1,domain,database-repl,database
    with open('.credentials', 'r') as f:
        file_data = f.read()
        #print read_data
        creds = file_data.split(',')
        user = creds[0]
        passw = creds[1]
        domain = creds[2]
        repldb = creds[3]
        dbname = creds[4].replace('\n','')


    credentials = {
      'user': user,
      'passw': passw,
      'domain': domain,
      'repldb': repldb,
      'db': dbname
    }

    setup_couchdb(credentials)
    start_key = int(time.time()*1000)-7*24*3600*1000
    result = db.view("_design/time/_view/last", startkey=start_key, descending=True)
    print "Documents to purge: ",len(result)
    arr_delete = []
    for row in result:
        arr_delete.append({'_id':row.id,'_rev':row.value})
    db.purge(arr_delete)
    print "Now compacting."
    if db.compact():
        print "Success"
    else:
        print "Error"
if __name__ == "__main__":
    main()
