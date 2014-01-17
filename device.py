#http://doughellmann.com/2007/12/pymotw-basehttpserver.html

from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
import threading
from Queue import Queue

import urlparse
import httplib
import json
import platform
from threading import Thread
from threading import Event
from threading import Lock, RLock
import time
import os
#import sys, traceback

class IORunMode:
	Standard, ImpulseCounter, EdgeCounter, RaisingEdgeCounter = range(0,4)

class IO(object):
	def __init__(self, iorep, name, label='', index=None):
		self._lock=RLock()
		self._iorep=iorep
		self._updateCount=0
		self._name=name
		self._value=0.0
		self._valueRaw=0
		self._stamp=0
		self._stampRaw=0
		self._unit=None
		self._error=False
		self._input=True
		self._retain=False
		self._label=label
		self._index=index
		self._runMode=IORunMode.Standard
		self._trigger=0
		self._stampUpdate=0

	@property
	def value(self):
		with self._lock:
			return self._value
	@value.setter
	def value(self, v):
		with self._lock:
			if self._valueRaw!=v:
				processedValue=self._processValue(v)
				self._valueRaw=v
				self._stampRaw=time.time()
				if self._value!=processedValue:
					self._value=processedValue
					self._trigger=1
					self._stamp=time.time()
				self.onUpdate() 

	@property
	def valueRaw(self):
		with self._lock:
			return self._valueRaw

	@property
	def runMode(self):
		with self._lock:
			return self._runMode

	def checkAndClearTrigger(self):
		with self._lock:
			trigger=False
			if self._trigger:
				trigger=True
				self._trigger=0
			return trigger

	@property
	def trigger(self):
		with self._lock:
			return self._trigger

	@property
	def stamp(self):
		with self._lock:
			return self._stamp

	@property
	def age(self):
		with self._lock:
			if self._stamp==0:
				return -1
			return time.time()-self._stamp

	@property
	def ageRaw(self):
		with self._lock:
			if self._stampRaw==0:
				return -1
			return time.time()-self._stampRaw
	@property
	def stampRaw(self):
		with self._lock:
			return self._stampRaw

	@property
	def ageUpdate(self):
		with self._lock:
			if self._stampUpdate==0:
				return -1
			return time.time()-self._stampUpdate

	def _processValue(self, value):
		return value

	def toggle(self):
		with self._lock:
			if self._value:
				self.value=0
			else:
				self.value=1

	@property
	def unit(self):
		with self._lock:
			return self._unit
	@unit.setter
	def unit(self, v):
		with self._lock:
			if not self._unit==v:
				self._unit=v
				self.onUpdate()

	@property
	def name(self):
		return self._name

	@property
	def label(self):
	    return self._label
	
	@property
	def index(self):
	    return self._index

	@property
	def updateCount(self):
	    return self._updateCount

	def isInput(self):
		return self._input

	def isOutput(self):
		return not self._input

	def onUpdate(self):
		with self._lock:
			self._iorep.onIOUpdated(self)
			self._stampUpdate=time.time()

	def dumpAsObject(self):
		data={'name': self.name, 'label':self.label, 
			'index':self.index, 'input':self.isInput(), 
			'value':self.value, 'unit':self.unit,
			'valueraw':self.valueRaw,
			'age':self.age, 
			'ageRaw':self.ageRaw, 
			'runmode':self.runMode,
			'updatecount':self.updateCount,
			'trigger':self.trigger}
		return data


class Input(IO):
	def __init__(self, iorep, name, label='', index=None):
		super(Input, self).__init__(iorep, name, label, index)
		self._input=True

	def setRunModeAsImpulseCounter(self):
		self._runMode=IORunMode.ImpulseCounter

	def setRunModeAsEdgeCounter(self):
		self._runMode=IORunMode.EdgeCounter

	def setRunModeAsRaisingEdgeCounter(self):
		self._runMode=IORunMode.RaisingEdgeCounter

	def _processValue(self, value):
		# already locked when called
		if self._runMode==IORunMode.Standard:
			self._updateCount+=1
			return value
		elif self._runMode==IORunMode.ImpulseCounter:
			if not bool(value) and bool(self.valueRaw):
				self._updateCount+=1
			return self._updateCount
		elif self._runMode==IORunMode.EdgeCounter:
			if bool(value) != bool(self.valueRaw):
				self._updateCount+=1
			return self._updateCount
		elif self._runMode==IORunMode.RaisingEdgeCounter:
			if bool(value) and not bool(self.valueRaw):
				self._updateCount+=1
			return self._updateCount

		print "Unimplemented IORunMode %d" % self._runMode
		return value

class Output(IO):
	def __init__(self, iorep, name, label='', index=None):
		super(Output, self).__init__(iorep, name, label, index)
		self._input=False

class IORepository(object):
	def __init__(self):
		self._lock=RLock()
		self._ios={}
		self._inputs={}
		self._outputs={}
		self._triggerRun=Event()
		self._triggerPoll=Event()
		self._pendingOutputWrite=[]
		self._pendingPoll=[]

	def backup(self):
		with self._lock:
			for io in self._ios.values():
				if io._retain:
					print "TODO: backup IO-%s %f" % (io.name, io.value)

	def restore(self):
		with self._lock:
			for io in self._ios.values():
				if io._retain:
					print "TODO: restore IO-%s" % io.name
		

	def addIO(self, io):
		try:
			name=io.name
			with self._lock:
				if not self.io(name):
					self._ios[name]=io
					if io.isInput():
						self._inputs[name]=io
					else:
						self._outputs[name]=io
				return io
		except:
			print "Unable to add IO"


	def createInput(self, name, label='', index=None):
		if index==None:
			index=len(self._inputs)
		return self.addIO(Input(self, name, label, index))

	def createOutput(self, name, label='', index=None):
		if index==None:
			index=len(self._outputs)
		return self.addIO(Output(self, name, label, index))

	def io(self, name):
		with self._lock:
			try:
				return self._ios[name]
			except:
				pass

	def input(self, name):
		with self._lock:
			try:
				return self._inputs[name]
			except:
				pass

	def inputs(self):
		ios=[]
		with self._lock:
			for io in self._inputs.values():
				ios.append(io)
		return ios

	def outputs(self):
		ios=[]
		with self._lock:
			for io in self._outputs.values():
				ios.append(io)
		return ios

	def ios(self, name=None):
		ios=[]
		with self._lock:
			if name:
				io=self.io(name)
				if io:
					ios.append(io)
			else:
				for io in self._ios.values():
					ios.append(io)
		return ios

	def output(self, name):
		with self._lock:
			try:
				return self._outputs[name]
			except:
				pass

	def onIOUpdated(self, io):
		if io.isOutput():
			if self.queuePendingOutputWrite(io):
				self.raiseTriggerRun()
		if self.queuePoll(io):
			self.raiseTriggerPoll()

	def raiseTriggerRun(self):
		self._triggerRun.set()

	def waitTriggerRun(self, timeout=0.1, reset=False):
		if self._triggerRun.wait(timeout):
			if reset:
				self._triggerRun.clear()
			return True

	def forceRefreshOutputs(self, maxAge=0):
		with self._lock:
			for io in self.outputs():
				if maxAge==0 or io.ageUpdate>maxAge:
					io.onUpdate()

	def queuePendingOutputWrite(self, io):
		with self._lock:
			if not io in self._pendingOutputWrite:
				self._pendingOutputWrite.append(io)
				return True

	def getPendingOutputWrite(self):
		with self._lock:
			try:
				io=self._pendingOutputWrite[0]
				del self._pendingOutputWrite[0] 
				return io 
			except:
				pass

	def raiseTriggerPoll(self):
		self._triggerPoll.set()

	def waitTriggerPoll(self, timeout=15):
		return self._triggerPoll.wait(timeout)

	def queuePoll(self, io):
		with self._lock:
			if not io in self._pendingPoll:
				self._pendingPoll.append(io)
				self._triggerPoll.set()
				return True

	def getPendingPoll(self):
		with self._lock:
			try:
				io=self._pendingPoll[0]
				del self._pendingPoll[0] 
				return io 
			except:
				pass
			self._triggerPoll.clear()

	def cancelTriggers(self):
		self.raiseTriggerRun()
		self.raiseTriggerPoll()


	def dumpAsObject(self):
		with self._lock:
			data=[]
			for io in self.ios():
				data.append(io.dumpAsObject())
			return data


class DeviceThread(Thread):
	def __init__(self, device):
		super(DeviceThread, self).__init__()
		self.name='DeviceThread'
		#self.daemon=True
		self._device=device
		self._eventStart=Event()
		self._eventStop=Event()
		self._onInit()

	@property
	def device(self):
		return self._device

	@property
	def iorep(self):
		return self.device.iorep

	def run(self):
		self._eventStart.set()
		while not self.isStopRequest():
			self._onRun()

	def stop(self):
		if not self.isStopRequest():
			self._eventStop.set()
			self._onStop()

	def release(self):
		self._onRelease()

	def waitUntilStarted(self):
		self._eventStart.wait()

	def isStopRequest(self):
		return self._eventStop.isSet()

	def _onInit(self):
		return self.onInit()

	def onInit(self):
		pass

	def _onRelease(self):
		return self.onRelease()

	def onRelease(self):
		pass

	def _onRun(self):
		return self.onRun()

	def onRun(self):
		time.sleep(0.1)

	def _onStop(self):
		return self.onStop()

	def onStop(self):
		pass

	def shutdownDevice(self):
		self.device.stop()



class HttpHandler(BaseHTTPRequestHandler):
	@property
	def device(self):
		return self.server.device

	@property
	def iorep(self):
		return self.device.iorep

	def getParam(self, qs, name, defaultValue=None):
		try:
			value=qs[name][0]
		except:
			value=defaultValue
		return value

	def getParamBool(self, qs, name, defaultValue=False):
		return bool(self.getParam(qs, name, defaultValue))

	def sendError(self, str):
		return self.send_error(404, str)

	def sendErrorRequestResponse(self):
		self.sendError('UNKNOWN:%s' % self.path)

	def sendJsonResponse(self, data):
		try:
			sdata=json.dumps(data)
			buf=sdata.encode()
			self.send_response(200)
			self.send_header('Content-type', 'application/json')
			self.send_header('Content-Length', str(len(buf)))
			self.end_headers()
			self.wfile.write(buf)
		except:
			pass

	def markAsHandler(method):
		method._requestHandler=True
		return method

	@markAsHandler
	def handler_get_info(self, qs):
		self.sendJsonResponse({'machine':platform.node(), 'os':platform.system()})

	@markAsHandler
	def handler_dump(self, qs):
		self.sendJsonResponse({'ios':self.iorep.dumpAsObject()})

	@markAsHandler
	def handler_read_state(self, qs):
		io=self.iorep.io(self.getParam(qs, 'name'))
		if io:
			data={'value':io.value, 'unit':io.unit}
			self.sendJsonResponse(data)

	@markAsHandler
	def handler_read_states(self, qs):
		data={}
		for io in self.iorep.ios():
			data[io.name]={'value':io.value, 'unit':io.unit}
		self.sendJsonResponse(data)

	@markAsHandler
	def handler_update_state(self, qs):
		io=self.iorep.output(self.getParam(qs, 'name'))
		if io:
			value=self.getParam(qs, 'value')
			try:
				io.value=float(value)
			except:
				pass
			unit=self.getParam(qs, 'unit', None)
			try:
				io.unit=int(unit)
			except:
				pass
			self.sendJsonResponse('success')

	@markAsHandler
	def handler_toggle_state(self, qs):
		io=self.iorep.output(self.getParam(qs, 'name'))
		if io:
			io.toggle()
			data={'value':io.value, 'unit':io.unit}
			self.sendJsonResponse(data)

	@markAsHandler
	def handler_poll(self, qs):
		if self.iorep.waitTriggerPoll(30):
			result={}
			while True:
				io=self.iorep.getPendingPoll()
				if not io:
					break
				data={'value':io.value, 'unit':io.unit}
				result[io.name]=data
			self.sendJsonResponse(result)
		else:	
			self.sendJsonResponse({})

	@markAsHandler
	def handler_list_item(self, qs):
		items=[]
		for io in self.iorep.inputs():
			items.append(io.name)
		for io in self.iorep.outputs():
			items.append(io.name)
		self.sendJsonResponse(items)

	@markAsHandler
	def handler_item_description(self, qs):
		items={}
		for io in self.iorep.ios(self.getParam(qs, 'name')):
			items[io.name]=io.label
		self.sendJsonResponse(items)

	@markAsHandler
	def handler_list_inputs(self, qs):
		items=[]
		for io in self.iorep.inputs():
			items.append(io.name)
		self.sendJsonResponse(items)

	@markAsHandler
	def handler_list_outputs(self, qs):
		items=[]
		for io in self.iorep.outputs():
			items.append(io.name)
		self.sendJsonResponse(items)

	@markAsHandler
	def handler_shutdown(self, qs):
		if self.device.isRemoteShutdownAllowed():
			self.sendJsonResponse({})
			self.server.shutdownDevice()
		else:
			self.sendErrorRequestResponse()

	@markAsHandler
	def handler_list_function(self, qs):
		data=[]
		for method in dir(self):
			if method[0:8]=='handler_':
				data.append(method[8:])
		self.sendJsonResponse(data)


	def do_GET(self):
		#self.log_request()
		rpath=urlparse.urlparse(self.path)
		qs=urlparse.parse_qs(rpath.query)

		handler='handler_'+rpath.path[1:]
		valid=False
		try:
	  		h=getattr(self, handler)
	  		if callable(h) and hasattr(h, '_requestHandler'):
	  			valid=True
	  	except:
	  		pass

	  	if valid:
  			return h(qs)

		self.sendErrorRequestResponse()


class WebServer(DeviceThread, ThreadingMixIn, HTTPServer):
	#important for shutdown (ThreadingMixIn property)
	daemon_threads=True

	def __init__(self, device, port, peerAddress=None):
		self._port=port
		self._peerAddress=peerAddress
		self._eventPoll=Event()
		DeviceThread.__init__(self, device)
		HTTPServer.__init__(self, ('', self._port), HttpHandler)

	def verify_request(self, request, client_address):
		if not self.device.isStopRequest():
			if not self._peerAddress:
				return True
			elif self._peerAddress==client_address[0]:
				return True
			print "Rejecting incoming http request from client %s" % client_address[0]
		return False

	def handle_timeout(self):
		pass

	def _onInit(self):
		self.name='WEB'
		self.request_queue_size=5
		self.timeout=15
		self.allow_reuse_address=True
		#self.daemon=True
		super(WebServer, self)._onInit()

	def _onRun(self):
		super(WebServer, self)._onRun()
		self.handle_request()

	def _onStop(self):
		super(WebServer, self)._onStop()
		try:
			c=httplib.HTTPConnection('localhost', self._port, timeout=2)
			c.request("GET", "/quit")
			c.close()
		except:
			pass


class SimpleTimer(object):
	def __init__(self, manager, delay, handler=None, topic=None):
		self._manager=manager
		self._topic=topic
		self._handler=handler
		self._delay=delay
		self._timeout=time.time()+delay

	def isTimeout(self):
		if time.time()>=self._timeout:
			return True
	@property
	def timeout(self):
	    return self._timeout

	@property
	def topic(self):
	    return self._topic

	def restart(self, delay=None):
		if delay==None:
	 		delay=self._delay
		self._timeout=time.time()+delay
	 	self._manager.add(self)

	def fire(self):
	 	handler=self._handler
	 	try:
		 	if not handler:
		 		handler=self._manager.onTimeout
		 	handler(self)
		except:
			pass

	def cancel(self):
		self._manager.remove(self)


class PeriodicTimer(SimpleTimer):
	def fire(self):
		super(PeriodicTimer, self).fire()
		self.restart()


class SimpleTimerManager(object):
	def __init__(self, target):
		self._lock=RLock()
		self._timers=[]
		self._target=target

	def timer(self, delay, handler=None, topic=None):
		timer=SimpleTimer(self, delay, handler, topic)
		return self.add(timer)

	def periodic(self, delay, handler=None, topic=None):
		timer=PeriodicTimer(self, delay, handler, topic)
		return self.add(timer)

	def add(self, timer):
		timeout=timer.timeout
		with self._lock:
			if self._timers:
				pos=0
				for t in self._timers:
					if timeout<t.timeout:
						self._timers.insert(pos, timer)
						return timer
					pos+=1
			self._timers.append(timer)
			return timer

	def remove(self, timer):
		try:
			self._timers.remove(timer)
		except:
			pass

	def manager(self):
		if self._timers:
			with self._lock:
				while self._timers[0].isTimeout():
					timer=self._timers[0]
					timer.fire()
					self.remove(timer)

class IOManager(DeviceThread):
	def _onInit(self):
		self.name='IO'
		self._timers=SimpleTimerManager(self)
		super(IOManager, self)._onInit()
		self.iorep.forceRefreshOutputs()
		self.periodicTimerWithHandler(15, self._onForceRefreshOutputs)

	def _onRelease(self):
		self.processPendingOutputWrite()
		super(IOManager, self)._onRelease()

	def timer(self, delay, topic=None):
		return self._timers.timer(delay, self.onTimeout, topic)

	def timerWithHandler(self, delay, handler, topic=None):
		return self._timers.timer(delay, handler, topic)

	def periodicTimer(self, delay, topic=None):
		return self._timers.periodic(delay, self.onTimeout, topic)

	def periodicTimerWithHandler(self, delay, handler, topic=None):
		return self._timers.periodic(delay, handler, topic)

	def onTimeout(self, timer):
		pass

	def _onStop(self):
		super(IOManager, self)._onStop()
		# cancel/fire waiting Trigger/Event, allowing fast exit
		self.iorep.cancelTriggers()
		self.iorep.backup()

	def _onForceRefreshOutputs(self, timer):
		self.iorep.forceRefreshOutputs(60)

	def processPendingOutputWrite(self):
		while True:
			io=self.iorep.getPendingOutputWrite()
			if not io:
				break
			with io._lock:
				self.onUpdateOutput(io)

	def _onRun(self):
		self.processPendingOutputWrite()
		self._timers.manager()
		if super(IOManager, self)._onRun():
			print "DEBUG: Triggering immediate IOManager run"
			self.iorep.raiseTriggerRun()

		# protective delay, just in case
		time.sleep(0.001)


	def onRun(self):
		self.sleep(1.0)

	def smartSleep(self, timeout):
		return self.sleep(timeout)

	def sleep(self, timeout):
		self.iorep.waitTriggerRun(timeout, True)

	def onUpdateOutput(self, io):
		return True

	def createInput(self, name, label='', index=None):
		io=self.iorep.createInput(name, label, index)
		return io

	def createOutput(self, name, label='', index=None):
		io=self.iorep.createOutput(name, label, index)
		return io

	def inputs(self):
		return self.iorep.inputs()
	
	def outputs(self):
		return self.iorep.outputs()

	def io(self, name):
		return self.iorep.io(name)

	def resetAllOutputs(self):
		for io in self.outputs():
			io.value=0


class Device(object):
	def __init__(self, iomanager, port=8000, peerAddress=None):
		print "Configuring device..."
		self._eventStop=Event()
		self._port=port
		self._iorep=IORepository()
		self._iomanager=iomanager(self)
		self._webserver=WebServer(self, port, peerAddress)
		self._peerAddress=None
		self._allowRemoteShutdown=False
		self._enableShutdownOnScriptUpdate=False
		self._stampFileMonitor={}
		self.addFileToScriptUpdateMonitor(__file__)

	@property
	def iorep(self):
		return self._iorep

	def allowRemoteShutdown(self, state=True):
		self._allowRemoteShutdown=state

	def enableShutdownOnScriptUpdate(self, state=True):
		self._enableShutdownOnScriptUpdate=state

	def addFileToScriptUpdateMonitor(self, f=__file__):
		try:
			self._stampFileMonitor[f]
		except:
			print "Adding file [%s] to script update monitor list" % f
			self._stampFileMonitor[f]=0

	def isRemoteShutdownAllowed(self):
		return self._allowRemoteShutdown

	def isStopRequest(self):
		return self._eventStop.isSet()

	def start(self):
		print "Starting device..."
		print "Starting device threads..."

		self._iomanager.start()
		self._iomanager.waitUntilStarted()

		self._webserver.start()
		self._webserver.waitUntilStarted()

		print "Device is now running."

		try:
			while not self._eventStop.wait(3):
				self.manager()
		except KeyboardInterrupt:
			print "Device halted by keyboard..."
			self.stop()
		except:
			print "Device halted by unhandled exception..."
			self.stop()
		finally:
			print "Waiting for device threads termination..."
			self._iomanager.join()
			self._webserver.join()
			print "Device threads halted."
			# for thread, frame in sys._current_frames().items():
			# 	print('Thread 0x%x' % thread)
			# 	traceback.print_stack(frame)
			print "Device halted."

	def manager(self):
		if self._enableShutdownOnScriptUpdate:
			try:
				for f,s in self._stampFileMonitor.items():
					stamp=os.path.getmtime(os.path.realpath(f))
					if s==0:
						self._stampFileMonitor[f]=stamp
					else:
						if stamp!=self._stampFileMonitor[f]:
							print "Device shutdown requested by file [%s] mtime monitoring..." % f
							time.sleep(2.0)
							self.stop()
			except:
				pass

		time.sleep(1.0)

	def stop(self):
		if not self._eventStop.isSet():	
			self._eventStop.set()
			print "Halting device threads..."
			self._iomanager.stop()
			self._webserver.stop()

			print "Releasing device threads..."
			self._iomanager.release()
			self._webserver.release()

	def dump(self):
		print "DEVICEDUMP"


if __name__ == '__main__':
	pass

