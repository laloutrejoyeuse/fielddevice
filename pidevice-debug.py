#!/usr/bin/python
from device import Device, IOManager
from pifacedigitalio import PiFaceDigital
from picamera import PiCamera
from PIL import Image
import io
import time
from threading import Event
import logging
from homematic import CCU


class MyIOManager(IOManager):
	def onInit(self):
		self.pf=PiFaceDigital()
		self.cam=PiCamera()
		self.cam.resolution=(640,480)

		# create inputs
		self.li0=self.createInput('i0')
		self.li0.setRunModeAsRaisingEdgeCounter()

		self.li1=self.createInput('i1')
		self.li1.setRunModeAsImpulseCounter()

		self.li2=self.createInput('i2')
		self.li2.setRunModeAsEdgeCounter()

		self.li3=self.createInput('i3')

		self.cam0=self.createJpegInput('im0')
		self.jobCam=self.job(self.piCamManager)
		self.eventShoot=Event()

		# create outputs
		self.lo0=self.createOutput('o0')
		self.lo1=self.createOutput('o1')

		self.ccu=self.job(self.ccuThread)

 
	def onRun(self):
		# process inputs
		self.li0.value=self.pf.input_pins[0].value
		self.li1.value=self.pf.input_pins[1].value
		self.li2.value=self.pf.input_pins[2].value
		self.li3.value=self.pf.input_pins[3].value

		# process outputs
		for io in self.inputs():
			if io.index<4 and io.checkAndClearTrigger():
				self.lo0.toggle()

		if self.li3.value:
			self.lo0.toggle()

		# keep CPU load as low as possible
		self.sleep(0.01)

	def onUpdateOutput(self, io):
		self.logger.debug("onUpdateOutput(%s)->%f" % (io.name, io.value))
		if io==self.lo0:
			self.pf.output_pins[0].value=io.value
		if io==self.lo1:
			self.pf.output_pins[1].value=io.value
			self.eventShoot.set()

	def onStop(self):
		# do a clean exit
		self.resetAllOutputs()

	def onRelease(self):
		self.cam.close()

	def piCamManager(self):
		while not self.isStopRequest():
			self.eventShoot.clear()
			#self.logger.debug('picam:capture...')
			stream=io.BytesIO()
			self.cam.led=1
			self.cam.capture(stream, format='jpeg')
			stream.seek(0)
			value=stream.getvalue()
			stream.close()
			self.cam0.value=value
			self.cam.led=0
			#self.eventShoot.wait(5)

	def ccuThread(self):
		ccu=CCU(self.name, 'http://192.168.0.29:2001', 'http://192.168.0.252:8077', self.logger)
		ccu.start()
		while not self.isStopRequest():
			notification=ccu.waitForNotification(3)
			if notification:
				try:
					if notification.key=='motion':
						ccu.logger.info(notification)
						self.lo1.value=bool(notification.value)
					else:
						ccu.logger.warning(notification)
				except:
					pass
		ccu.stop()

	

dev=Device('https://192.168.2.1/rws/api/dcf', 
	's_STDEMO_fd2', 
	'BFEBB90A6F1876531F14225D6AAF3BE0', 
	MyIOManager,
	'192.168.0.84',
	logging.DEBUG)

dev.addFileToScriptUpdateMonitor(__file__)
dev.enableShutdownOnScriptUpdate()

dev.start()
