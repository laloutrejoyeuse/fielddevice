import time
from threading import RLock

class VIO(object):
	def __init__(self):
		self._lock=RLock()
		self._value=0
		self._stamp=time.time()
		self._timeout=0

	@property
	def value(self):
		with self._lock:
			self._manager()
	    	return self._value
	@value.setter
	def value(self, value):
		with self._lock:
			value=self._processValue(value)
			if value!=self._value:
				self._stamp=time.time()
				self._value=value

	def age(self):
		return time.time()-self._stamp

	def _setTimeout(self, delay):
		with self._lock:
			self._timeout=time.time()+delay

	def _isTimeout(self):
		with self._lock:
			return time.time()>=self._timeout

	def _processValue(self, value):
		return value

	def _manager(self):
		pass


class VDout(VIO):
	def __init__(self, t01, t10):
		super(VDout, self).__init__()
		self._t01=float(t01)
		self._t10=float(t10)
		self._targetValue=0
		self.value=0

	def _manager(self):
		if self._isTimeout() and self._value!=self._targetValue:
			self._value=self._targetValue

	def _processValue(self, value):
		if value:
			value=1
		else:
			value=0
		if value!=self._targetValue:
			self._targetValue=value
			if value:
				self._setTimeout(self._t01)
			else:
				self._setTimeout(self._t10)
		self._manager()
		return self._value


class VImpulse(VIO):
	def __init__(self, delay):
		super(VImpulse, self).__init__()
		self._delay=float(delay)
		self._targetValue=0
		self.value=0

	def pulse(self):
		self.value=1

	def reset(self):
		self.value=0

	def _manager(self):
		if self._value and self._isTimeout():
			self._value=0

	def _processValue(self, value):
		if value:
			self._setTimeout(self._delay)
			return 1
		return self._value


class VOscillator(VIO):
	def __init__(self, t0, t1):
		super(VOscillator, self).__init__()
		self._t0=float(t0)
		self._t1=float(t1)
		self.value=0

	def _manager(self):
		if self._isTimeout():
			if self._value:
				self._value=0
				self._setTimeout(self._t0)
			else:
				self._value=1
				self._setTimeout(self._t1)




