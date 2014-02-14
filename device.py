#http://doughellmann.com/2007/12/pymotw-basehttpserver.html

from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
#from SocketServer import ThreadingMixIn
import urllib
from Queue import Queue

import urlparse
import httplib
import json
import platform
import threading
from threading import Thread
from threading import Event
from threading import Lock, RLock
from threading import Timer
import time
import os
import requests
import math
import sys, traceback
import logging, logging.handlers
import base64
#import colorer

DEVICE_VERSION='0.2.1'

class IORunMode:
	Standard, ImpulseCounter, EdgeCounter, RaisingEdgeCounter = range(0,4)

class IOIrqMode:
	Ignore, Change, Delta = range(0,3) 

class IO(object):
	def __init__(self, iorep, name, label='', index=None):
		self._lock=RLock()
		self._iorep=iorep
		self._name=name
		self._updateCount=0
		self._value=0.0
		self._valueRaw=0
		self._stamp=0
		self._unit=None
		self._error=False
		self._input=True
		self._retain=False
		self._label=label
		self._index=index
		self._runMode=IORunMode.Standard
		self._irqMode=IOIrqMode.Change
		self._irqDelta=0.5
		self._irqValue=0
		self._trigger=0
		self._stampUpdate=0

	@property
	def logger(self):
		return self.device.logger

	@property
	def iorep(self):
		return self._iorep

	@property
	def device(self):
		return self.iorep.device

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
		with self._lock:
			return self._updateCount

	@property
	def irqMode(self):
		return self._irqMode

	@irqMode.setter
	def irqMode(self, value):
		self._irqMode = value

	def isInput(self):
		return self._input

	def isOutput(self):
		return not self._input

	def onUpdate(self):
		with self._lock:
			irq=False
			if self._irqMode!=IOIrqMode.Ignore:
				if self._irqMode==IOIrqMode.Change:
					irq=True
				elif self._irqMode==IOIrqMode.Delta:
					if math.fabs(self._value-self._irqValue)>=self._irqDelta:
						irq=True
				if irq:
					self._irqValue=self._value
			self._iorep.onIOUpdated(self, irq)
			self._stampUpdate=time.time()

	def dumpAsObject(self):
		data={'name': self.name, 'label':self.label, 
			'index':self.index, 'input':self.isInput(),
			'value':self.value, 'unit':self.unit,
			'valueraw':self.valueRaw,
			'age':self.age, 
			'runmode':self.runMode,
			'updatecount':self.updateCount,
			'trigger':self.trigger}
		return data

	def __repr__(self):
		return str(self.dumpAsObject())

	def enableIrq(self):
		self.setIrqDelta(0)

	def setIrqDelta(self, delta):
		with self._lock:
			if delta<=0:
				self._irqMode=IOIrqMode.Change
			else:
				self._irqMode=IOIrqMode.Delta
				self._irqDelta=delta
				self._irqValue=self._value

	def disableIrq(self):
		with self._lock:
			self._irqMode=IOIrqMode.Ignore

	def valueObject(self):
		with self._lock:
			value=self._value
			data={'name':self._name, 'value':value, 'unit':self._unit}
			return data

class IOSimple(IO):
	pass

class Input(IOSimple):
	def __init__(self, iorep, name, label='', index=None):
		super(Input, self).__init__(iorep, name, label, index)
		self._input=True
		self.logger.debug('Creating Input %s...' % self.name)

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

		self.logger.error("Unimplemented IORunMode %d" % self._runMode)
		return value


class Output(IOSimple):
	def __init__(self, iorep, name, label='', index=None):
		super(Output, self).__init__(iorep, name, label, index)
		self._input=False
		self.logger.debug('Creating Output %s...' % self.name)


class BinaryInput(IOSimple):
	def __init__(self, iorep, name, contentType, label='', index=None):
		super(BinaryInput, self).__init__(iorep, name, label, index)
		self._contentType=contentType
		self._input=True
		self._irqMode=IOIrqMode.Ignore
		self.logger.debug('Creating B64Binary/%s/Input %s...' % (contentType, self.name))

	def _processValue(self, value):
		# already locked when called
		try:
			return base64.b64encode(value)
		except:
			self.logger.error("Unable to encode value to base64!")
			return self._value

	def valueObject(self):
		with self._lock:
			return {'name':self._name, 'value':self._value, 'content':self._contentType, 'encoding':'b64'}

class IORepository(object):
	def __init__(self, device):
		self._lock=RLock()
		self._device=device
		self._stampInit=time.time()
		self._ios={}
		self._inputs={}
		self._outputs={}

		self._triggerRun=Event()
		self._triggerIrq=Event()
		self._pendingOutputWrite=[]
		self._pendingIrq=[]

	@property
	def logger(self):
		return self.device.logger
	
	@property
	def device(self):
		return self._device
	
	@property
	def uptime(self):
		with self._lock:
			return time.time()-self._stampInit

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
				if not self.ioexists(name):
					self._ios[name]=io
					if io.isInput():
						self._inputs[name]=io
					else:
						self._outputs[name]=io
				return io
		except:
			self.logger.error("Unable to register IO %s" % io.name)

	def createInput(self, name, label='', index=None):
		if index==None:
			index=len(self._inputs)
		return self.addIO(Input(self, name, label, index))

	def createBinaryInput(self, name, contentType, label='', index=None):
		if index==None:
			index=len(self._inputs)
		return self.addIO(BinaryInput(self, name, contentType, label, index))

	def createOutput(self, name, label='', index=None):
		if index==None:
			index=len(self._outputs)
		return self.addIO(Output(self, name, label, index))

	def ioexists(self, name):
		with self._lock:
			try:
				if self._ios[name]:
					return True
			except:
				pass

	def io(self, name):
		with self._lock:
			try:
				return self._ios[name]
			except:
				self.logger.warning('unable to retrieve io %s' % name)

	def input(self, name):
		with self._lock:
			try:
				return self._inputs[name]
			except:
				self.logger.warning('unable to retrieve input %s' % name)

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
				self.logger.warning('unable to retrieve output %s' % name)

	def onIOUpdated(self, io, irq=True):
		if io.isOutput():
			if self.queuePendingOutputWrite(io):
				self.raiseTriggerRun()
		if irq and self.queueIrq(io):
			self.raiseTriggerIrq()

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

	def raiseTriggerIrq(self):
		self._triggerIrq.set()

	def waitTriggerIrq(self, timeout=15):
		if timeout:
			return self._triggerIrq.wait(timeout)
		return self._triggerIrq.isSet()

	def queueIrq(self, io):
		with self._lock:
			if not io in self._pendingIrq:
				self._pendingIrq.append(io)
				self._triggerIrq.set()
				return True

	def getPendingIrq(self):
		with self._lock:
			try:
				io=self._pendingIrq[0]
				del self._pendingIrq[0] 
				return io 
			except:
				# list is empty
				self._triggerIrq.clear()

	def cancelTriggers(self):
		self.raiseTriggerRun()
		self.raiseTriggerIrq()

	def dumpAsObject(self):
		with self._lock:
			data=[]
			for io in self.ios():
				data.append(io.dumpAsObject())
			return data


class SimpleTimer(object):
	def __init__(self, manager, delay, handler):
		self._manager=manager
		self._handler=handler
		self._delay=delay
		self._timeout=time.time()+delay

	def isTimeout(self):
		if time.time()>=self._timeout:
			return True
	@property
	def timeout(self):
		return self._timeout

	def restart(self, delay=None):
		if delay==None:
			delay=self._delay
		self._timeout=time.time()+delay
		self._manager.add(self)

	def fire(self):
		try:
			#print "fire %s" % self._handler.__name__
			self._handler()
		except:
			pass

	def cancel(self):
		self._manager.remove(self)


class PeriodicTimer(SimpleTimer):
	def fire(self):
		super(PeriodicTimer, self).fire()
		self.restart()


class SimpleTimerManager(object):
	def __init__(self):
		self._lock=RLock()
		self._timers=[]

	def timer(self, delay, handler):
		timer=SimpleTimer(self, delay, handler)
		return self.add(timer)

	def periodic(self, delay, handler):
		timer=PeriodicTimer(self, delay, handler)
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

	def removeAll(self):
		while self._timers:
			timer=self._timers[0]
			self.remove(timer)

	def manager(self):
		if self._timers:
			with self._lock:
				while self._timers[0].isTimeout():
					timer=self._timers[0]
					timer.fire()
					self.remove(timer)


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
	def logger(self):
		return self.device.logger

	@property
	def device(self):
		return self._device

	@property
	def iorep(self):
		return self.device.iorep

	def start(self):
		super(DeviceThread, self).start()
		self._onStart()

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

	def _onStart(self):
		return self.onStart()

	def onStart(self):
		pass

	def _onRun(self):
		return self.onRun()

	def onRun(self):
		time.sleep(0.1)

	def _onStop(self):
		return self.onStop()

	def onStop(self):
		pass



class DcfMessage(object):
	def __init__(self, msgType, data=None):
		if not data:
			data={}
		self._data=data
		self.type=msgType

	@property
	def type(self):
		return self._data['type']
	@type.setter
	def type(self, value):
		self._data['type'] = value
	
	@property
	def data(self):
		return self._data
	@data.setter
	def data(self, value):
		self._data = value

	def json(self):
		data=self._data
		data['type']=self._type
		return json.dumps(data)

	def __getitem__(self, key):
		try:
			return self._data[key]
		except:
			return None


class DcfManager(DeviceThread):
	def onInit(self):
		self.name='DcfManagerIO'
		self._url=self.device.url
		self._queueMsgIn=Queue()
		self._queueMsgOut=Queue()

		self._threadPoll=threading.Thread(target=self.pollThread)
		self._threadPoll.start()
		self.queueMessage(DcfMessage('SyncRequest'))

	def messageHandler(method):
		method._messageHandler=True
		return method

	@messageHandler
	def onSetStateRequest(self, message):
		io=self.iorep.io(message['name'])
		if io:
			try:
				value=message['value']
				if type(value) is dict:
					print "TODO: decode dict/value"
				else:
					io.value=float(value)
					io.unit=message['unit']
					self.logger.debug("onSetStateRequest(%s=%f)" % (io.name, io.value))
			except:
				self.logger.error("Exception occured during onSetStateRequest()")

	@messageHandler
	def onGetStateRequest(self, message):
		io=self.iorep.io(message['name'])
		if io:
			self.queueMessage(DcfMessage('GetStateResponse', io.valueObject()))

	@messageHandler
	def onRestartRequest(self, message):
		if self.device.isRemoteShutdownAllowed():
			self.logger.info("Shutdown requested by peer.")
			self.device.stop()

	def queueMessage(self, message):
		if message:
			self._queueMsgOut.put(message)
			self.iorep.raiseTriggerIrq()

	def dispatchMessagesToServer(self):
		messages=[]
		while 1:
			try:
				message=self._queueMsgOut.get(False)
				if message:
					messages.append(message.data)
			except:
				break

		if messages:
			try:
				data=json.dumps({'messages':messages})
				p={'h':self.device.auth, 'src':self.device.lkey, 'dest':self.device.key, 'query':'send/device'}
				self.logger.debug("send/device(%s)" % ((data[:150] + '...') if len(data) > 150 else data))
				r=requests.post(self._url, params=p, timeout=15.0, allow_redirects=True, verify=False, data=data)
				if not r or r.status_code != requests.codes.ok:
					self.logger.error("Abnormal http result %d received while flushing txqueue [%s]!" % (r.status_code, self._url))
			except requests.exceptions.ConnectionError:
				self.logger.error("HTTPError while sending message to server!")
			except requests.exceptions.HTTPError:
				self.logger.error("HTTPError while sending message to server!")
			except:
				self.logger.error("RequestException occured while sending message to server!")

	def onRun(self):
		# block until stop, irq or rx-message via pollThread
		self.iorep.waitTriggerIrq(15.0)

		# ---- RX Manager
		while 1:
			try:
				message=self._queueMsgIn.get(False)
				handler='on'+message.type

				valid=False
				try:
					h=getattr(self, handler)
					if callable(h) and hasattr(h, '_messageHandler'):
						h(message)
				except:
					self.logger.error("Exception occured while handling message!")
			except:
				break

		# ---- TX Manager
		self.dispatchMessagesToServer()

		# ---- Irq Manager
		messages=[]
		while 1:
			io=self.iorep.getPendingIrq()
			if not io:
				break

			message=DcfMessage('SignalStateRequest', io.valueObject())
			messages.append(message)

		if messages:
			for message in messages:
				self._queueMsgOut.put(message)
	
			# simulate IRQ trigger to force manager run
			self.iorep.raiseTriggerIrq()

	def pollThread(self):
		self.logger.info("Polling thread started.")
		url=self._url
		p={'h':self.device.auth, 'src':self.device.lkey, 'dest':self.device.key, 'query':'poll/device', 'timeout':30}

		while not self.isStopRequest():
			try:
				r=requests.post(url, params=p, timeout=45, allow_redirects=True, verify=False)
				if r and r.status_code == requests.codes.ok:
					req=r.json()
					if req:
						try:
							for m in req['messages']:
								message=DcfMessage(m['type'], m)
								self._queueMsgIn.put(message)
						except:
							self.logger.error("Malformed poll response received!")

					# simulate IRQ trigger to force manager run
					self.iorep.raiseTriggerIrq()
			except:
				self.logger.error("Exception occured during polling thread!")
				time.sleep(5.0)

		self.logger.info("Polling thread halted.")


	def onStop(self):		
		# fake sync (buggy?) to close as soon as possible the poll thread
		self.queueMessage(DcfMessage('SyncRequest'))
		self.dispatchMessagesToServer()
		self.logger.info("Waiting for polling thread termination...")
		self._threadPoll.join()


class IOJob(object):
	def __init__(self, jobmanager, target):
		self._name=target.__name__
		self._jobmanager=jobmanager
		self._target=target
		self._eventStop=Event()
		self._thread=Thread(target=self._manager)

	@property
	def name(self):
		return self._name
	
	@property
	def jobmanager(self):
		return self._jobmanager

	@property
	def device(self):
		return self.jobmanager.device

	@property
	def logger(self):
		return self.device.logger

	def waitForExit(self):
		self.stop()
		self.logger.debug("IOJOB(%s):wait for thread termination" % self.name)
		self._thread.join()
		self.logger.info("IOJOB(%s):done" % self.name)

	def start(self):
		self._thread.start()

	def _manager(self):
		self.logger.info("IOJOB(%s):manager started" % self.name)
		try:
			self._target()
			time.sleep(0.01)
		except:
			self.logger.error("IOJOB(%s):exception occured during job execution" % self.name)
			time.sleep(5)    			
		self.logger.info("IOJOB(%s):manager stopped" % self.name)
		self.jobmanager.signalExited(self)

	def stop(self):
		if not self._eventStop.isSet():
			self._eventStop.set()
			self.logger.debug("IOJOB(%s):stop request!" % self.name)


class IOJobManager(object):
	def __init__(self, device):
		self._lock=RLock()
		self._jobs=[]
		self._queueExitedJob=Queue()
		self._device=device

	@property
	def device(self):
		return self._device

	@property
	def logger(self):
		return self.device.logger

	def create(self, target):
		job=IOJob(self, target)
		with self._lock:
			self._jobs.append(job)
			return job

	def signalExited(self, job):
		self._queueExitedJob.put(job)

	def jobs(self):
		return self._jobs

	def start(self):
		with self._lock:
			for job in self.jobs():
				job.start()

	def stop(self):
		with self._lock:
			for job in self.jobs():
				job.stop()

		self.logger.debug('JOBS: waiting for jobs termination...')
		while len(self._jobs)>0:
			self.manager()
			time.sleep(0.1)
		self.logger.debug('JOBS: gracefully exited.')

	def _jobClean(self, job):
		if job:
			job.waitForExit()
			with self._lock:
				if job in self._jobs:
					self._jobs.remove(job)
					self.logger.debug('IOJOB(%s): unregistered.' % job.name)

	def manager(self):
		try:
			job=self._queueExitedJob.get_nowait()
			self._jobClean(job)
		except:
			pass


class IOManager(DeviceThread):
	def _onInit(self):
		self.name='IOManager'
		self._timers=SimpleTimerManager()
		self._jobs=IOJobManager(self)
		super(IOManager, self)._onInit()
		self.iorep.forceRefreshOutputs()

	def _onRelease(self):
		self.processPendingOutputWrite()
		super(IOManager, self)._onRelease()

	def job(self, target):
		return self._jobs.create(target)

	def timer(self, delay, handler):
		return self._timers.timer(delay, handler)

	def periodicTimer(self, delay, handler):
		return self._timers.periodic(delay, handler)

	def _onStart(self):
		super(IOManager, self)._onStart()
		self._jobs.start()

	def _onStop(self):
		super(IOManager, self)._onStop()
		# cancel/fire waiting Trigger/Event, allowing fast exit
		self._jobs.stop()
		self._timers.removeAll()
		self.iorep.cancelTriggers()
		self.iorep.backup()

	#def _onForceRefreshOutputs(self, timer):
	#	self.iorep.forceRefreshOutputs(60)

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
		self._jobs.manager()
		if super(IOManager, self)._onRun():
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

	def createBinaryInput(self, name, contentType, label='', index=None):
		io=self.iorep.createBinaryInput(name, contentType, label, index)
		return io

	def createJpegInput(self, name, label='', index=None):
		io=self.iorep.createBinaryInput(name, 'image/jpeg', label, index)
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
	def __init__(self, url, key, auth, iomanager, logServer='localhost', logLevel=logging.DEBUG):
		logger=logging.getLogger("DEVICE-%s" % key)
		logger.setLevel(logLevel)
		socketHandler = logging.handlers.SocketHandler(logServer, logging.handlers.DEFAULT_TCP_LOGGING_PORT)
		logger.addHandler(socketHandler)
		self._logger=logger

		# ch = logging.StreamHandler()
		# ch.setLevel(logLevel)
		# formatter = logging.Formatter('%(asctime)s:%(name)s::%(levelname)s::%(message)s')
		# ch.setFormatter(formatter)
		# logger.addHandler(ch)

		self.logger.info("Configuring device [%s@%s]..." % (key, url))

		self._key=key
		self._lkey=key + ".device"
		self._url=url
		self._auth=auth
		self._eventStop=Event()
		self._iorep=IORepository(self)
		self._allowRemoteShutdown=False
		self._enableShutdownOnScriptUpdate=False
		self._stampFileMonitor={}
		self.addFileToScriptUpdateMonitor(__file__)

		self._iomanager=iomanager(self)
		self._dcfmanager=DcfManager(self)

	@property
	def logger(self):
		return self._logger

	@property
	def iorep(self):
		return self._iorep

	@property
	def key(self):
		return self._key

	@property
	def lkey(self):
		return self._lkey

	@property
	def name(self):
	    return self._lkey

	@property
	def url(self):
		return self._url
	
	@property
	def auth(self):
		return self._auth

	def allowRemoteShutdown(self, state=True):
		self._allowRemoteShutdown=state

	def enableShutdownOnScriptUpdate(self, state=True):
		self._enableShutdownOnScriptUpdate=state

	def addFileToScriptUpdateMonitor(self, f=__file__):
		try:
			if f[-4:]=='.pyc':
				f=f[0:-4]+'.py'
			self.logger.info("Adding file [%s] to script update monitor list" % f)
			self._stampFileMonitor[f]=0
		except:
			pass

	def isRemoteShutdownAllowed(self):
		return self._allowRemoteShutdown

	def isStopRequest(self):
		return self._eventStop.isSet()

	def start(self):
		self.logger.info("Starting device...")
		self.logger.info("Starting device threads...")
		self._iomanager.start()
		self._iomanager.waitUntilStarted()
		self._dcfmanager.start()
		self._dcfmanager.waitUntilStarted()
		self.logger.info("Device is now running.")

		try:
			while not self._eventStop.wait(3):
				self.manager()
		except KeyboardInterrupt:
			msg="Device halted by keyboard..."
			print msg
			self.logger.info(msg)
			self.stop()
		except:
			self.logger.info("Device halted by unhandled exception...")
			self.stop()
		finally:
			self.logger.info("Waiting for device threads termination...")
			self._iomanager.join()
			self._dcfmanager.join()
			self.logger.info("Device threads halted.")
			# for thread, frame in sys._current_frames().items():
			# 	print('Thread 0x%x' % thread)
			# 	traceback.print_stack(frame)
			self.logger.info("Device halted.")

	def manager(self):
		if self._enableShutdownOnScriptUpdate:
			try:
				for f,s in self._stampFileMonitor.items():
					stamp=os.path.getmtime(os.path.realpath(f))
					if s==0:
						self._stampFileMonitor[f]=stamp
					else:
						if stamp!=self._stampFileMonitor[f]:
							self.logger.info("Device shutdown requested by file [%s] mtime monitoring..." % f)
							time.sleep(3.0)
							self.stop()
							break
			except:
				pass
		self.sleep(3.0)

	def sleep(self, delay):
		self._eventStop.wait(delay)

	def stop(self):
		if not self._eventStop.isSet():	
			self._eventStop.set()

			self.logger.info("Halting device threads...")
			self._iomanager.stop()
			self._dcfmanager.stop()

			self.logger.info("Releasing device threads...")
			self._iomanager.release()
			self._dcfmanager.release()

	def dump(self):
		pass


if __name__ == '__main__':
	pass

