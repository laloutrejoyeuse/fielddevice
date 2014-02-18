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

	def pipe(self, value):
		with self._lock:
			self.value=value
			return self.value


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


class Impulse(VIO):
	def __init__(self, delay):
		super(Impulse, self).__init__()
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


class Oscillator(VIO):
	def __init__(self, t0, t1):
		super(Oscillator, self).__init__()
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


class Chenillard(VIO):
	def __init__(self, size, delay=1):
		super(Chenillard, self).__init__()
		if isinstance(size, (list, tuple)):
			self._items=size
			self._size=len(size)
		else:
			self._items=None
			self._size=size
		self._delay=delay
		self._loop=0
		self._value=-1

	def __getitem__(self, i):
		with self._lock:
			self._manager()
			if i>=0 and i<self._size and self._value==int(i):
				return 1
			return 0

	def channels(self):
		with self._lock:
			self._manager()
			values=[0 for x in range(self._size)]
			if self.isActive():
				values[self._value]=1
			return values

	def items(self):
		return self._items

	def itemActive(self):
		try:
			with self._lock:
				self._manager()
				if self.isActive() and self._items:
					return self._items[self._value]
		except:
			pass

	def __repr__(self):
		return str(self.channels())

	def _manager(self):
		if self.isActive() and self._isTimeout():
			self._value+=1
			if self._value<self._size:
				self._setTimeout(self._delay)
			else:
				if self._loop>0:
					self._loop-=1
					self._value=0
					self._setTimeout(self._delay)
				else:
					self._value=-1

	def _processValue(self, value):
		return self._value

	def start(self, count=1):
		with self._lock:
			if count>0:
				self._loop=count-1
				self._value=0
				self._setTimeout(self._delay)
			else:
				self.stop()

	def isActive(self):
		return self._value>=0

	def stop(self):
		with self._lock:
			self._loop=0
			self._value=-1


class RisingEdge(VIO):
	def __init__(self):
		super(RisingEdge, self).__init__()

	def _processValue(self, value):
		if value:
			return self._value+1
		return self._value

	@VIO.value.getter
	def value(self):
		with self._lock:
			value=self._value
			self._value=0
			return value


class Edge(VIO):
	def __init__(self):
		super(Edge, self).__init__()
		self._rawValue=0

	def _processValue(self, value):
		if value:
			value=1
		else:
			value=0
		if value!=self._rawValue:
			self._rawValue=value
			return self._value+1
		return self._value

	@VIO.value.getter
	def value(self):
		with self._lock:
			value=self._value
			self._value=0
	    	return value



