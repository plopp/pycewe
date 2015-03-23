#!/usr/bin/env python
# -*- coding: utf-8 -*-

import couchdb
import time
import sys,os

os.chdir("/home/marcus/git/pycewe/")
couch = None
db = None
def setup_couchdb(credentials):
   global couch
   global db
   couch = couchdb.Server("http://127.0.0.1:5984" % credentials)
   couch.resource.credentials = ('%(user)s' % credentials,"%(passw)s" % credentials)
   db = couch['%(db)s' % credentials] # existing

def main():

    #There is got to be a text file named ".credentials" in the same folder as the
    #python script, containg: <user>,<passw>,<domain>,<repldb_name>,<dbname>
    #example: user1,password1,domain,database-repl,database
    with open('.credentials_local', 'r') as f:
        file_data = f.read()
        #print read_data
        creds = file_data.split(',')
        user = creds[0]
        passw = creds[1]
        protocol = creds[2]
        domain = creds[3]
        dbname = creds[4].replace('\n','')


    credentials = {
      'user': user,
      'passw': passw,
      'domain': domain,
      'protocol' : protocol,
      'db': dbname
    }
    print credentials

    setup_couchdb(credentials)
    start_key = int(time.time()*1000)-2*3600*1000
    #start_key = int(time.time()*1000)-1*60*1000
    print start_key
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
