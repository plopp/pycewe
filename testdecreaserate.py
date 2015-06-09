import threading
import Queue
import time

addr_q = Queue.Queue()
reply_q = Queue.Queue()

i1 = 9
i2 = 9
data1_1 = None #192.168.1.3
data1_2 = None #192.168.1.4
def read_data(q,reply_q):
	global data1_1,data1_2,i1,i2
	#print "Running read_data"
	s = q.get()
	name = s[0]
	try:
		if name == "192.168.1.3":
		    i1 = i1 + 1
		if name == "192.168.1.4":
		    i2 = i2 + 1
		if i1 > 9 and name == "192.168.1.3":
		    data1_1 = time.time()
		    i1 = 0
		if i2 > 9 and name == "192.168.1.4":
		    data1_2 = time.time()
		    i2 = 0
		data1 = None
		if name == "192.168.1.3":
		    data1 = data1_1
		    print "Here1"
		elif name == "192.168.1.4":
		    data1 = data1_2
		    print "Here2"

		data = {
			"data1":data1,
			"time":time.time(),
			"unit":name
		}
		reply_q.put(data);
		q.task_done()
	except:
		raise

def main():
	try:
		while True:
			t0 = time.time()
			thread1 = threading.Thread(target=read_data,args=(addr_q,reply_q,))
			thread2 = threading.Thread(target=read_data,args=(addr_q,reply_q,))
			thread1.start()
			thread2.start()
			addr_q.put(["192.168.1.3"])
			addr_q.put(["192.168.1.4"])
			addr_q.join()

			print reply_q.get(block=True)
			print reply_q.get(block=True)
			print "Done."
			time.sleep(1)
	except:
		raise

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise