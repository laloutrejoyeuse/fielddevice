#!/usr/bin/python
import logging
from device import Device, IOManager
from threading import Event
import time

from pifacedigitalio import PiFaceDigital
from homematic import CCU
from vio import VDout, VImpulse

class MyIOManager(IOManager):
	def onInit(self):
		self.alarmEnable=self.createOutput('i0')
		self.alarmPreEnable=self.createOutput('i1')
		self.intrusion=self.createOutput('i2')
		self.day=self.createOutput('i3')

		self.lightFHE=self.createInput('o0')
		self.lightFHE_DCH=self.createInput('o1')
		self.lightDCH=self.createInput('o2')
		self.lightKITCHEN=self.createInput('o3')
		self.lightENTRANCE=self.createInput('o4')
		self.lightCONFERENCE=self.createInput('o5')

		# self.irFHE_DCH=self.createInput('ir0')
		# self.irDCH_KITCHEN=self.createInput('ir1')
		# self.irKITCHEN_ENTRANCE=self.createInput('ir2')
		# self.irENTRANCE_CONFERENCE=self.createInput('ir3')

		self.lightTimer=VImpulse(60)

		self.job(self.ccuThread)

 
	def onRun(self):
		#state=bool(int(time.time()) % 5)
		self.lightFHE.value=self.lightTimer.value or self.intrusion.value

		# keep CPU load as low as possible
		self.sleep(0.01)

	def onUpdateOutput(self, io):
		self.logger.debug("onUpdateOutput(%s)->%f" % (io.name, io.value))

	def onStop(self):
		# do a clean exit
		self.resetAllOutputs()

	def onRelease(self):
		pass

	def ccuThread(self):
		ccu=CCU(self.name, 'http://192.168.0.29:2001', 'http://192.168.0.252:8077', self.logger)
		ccu.start()
		while not self.isStopRequest():
			notification=ccu.waitForNotification(3)
			if notification:
				try:
					if notification.key=='motion' and notification.value:
						ccu.logger.info(notification)
						if notification.isSource(['jeq0701960:1', 'keq0362887:1']):
							self.lightTimer.pulse()
					else:
						ccu.logger.warning(notification)
				except:
					pass
		ccu.stop()

	

dev=Device('https://192.168.2.1/rws/api/dcf', 
	's_112_alarming', 
	'BFEBB90A6F1876531F14225D6AAF3BE0', 
	MyIOManager,
	'192.168.0.84',
	logging.DEBUG)

dev.addFileToScriptUpdateMonitor(__file__)
dev.enableShutdownOnScriptUpdate()

dev.start()
