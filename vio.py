import time
from threading import RLock



class VIO(object):
	def __init__(self):
		self._lock=RLock()
		self._value=0
		self._stamp=0
		self._timeout=0

	@property
	def value(self):
		with self._lock:
	    	return self._value
	@value.setter
	def value(self, value):
		with self._lock:
	    	self._value = value

	def setTimeout(self, delay):
		with self._lock:
			self._timeout=time.time()+delay

	def isTimeout(self):
		with self._lock:
			return time.time()>=self._timeout









	


class VDout(object):
	def __init__(self, t01, t10):
		self._value=0
		self._stamp=0
