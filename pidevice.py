#!/usr/bin/python
import logging
from device import Device, IOManager
from threading import Event
import time

from pifacedigitalio import PiFaceDigital
from homematic import CCU
from vio import *


# clean : io labels --> useless
# todo : io labels-->group (i.e. "lights")
# todo: get ios by names (i.e. inputs('lights'))

class MyIOManager(IOManager):
	def onInit(self):
		self.alarmEnable=self.createOutput('i0')
		self.alarmPreEnable=self.createOutput('i1')
		self.intrusion=self.createOutput('i2')
		self.day=self.createOutput('i3')

		self.lightFHE=self.createInput('o0', 'light')
		self.lightFHE_DCH=self.createInput('o1', 'light')
		self.lightDCH=self.createInput('o2', 'light')
		self.lightKITCHEN=self.createInput('o3', 'light')
		self.lightENTRANCE=self.createInput('o4', 'light-reserve')
		self.lightCONFERENCE=self.createInput('o5', 'light-reserve')
		self.chenillard=Chenillard(self.inputs('light'), 1)
		self.chenillard.start(10)

		self.irSALEVE=self.createInput('ir0')
		self.timerSALEVE=Impulse(120)

		self.irVOIRONS=self.createInput('ir1')
		self.timerVOIRONS=Impulse(120)

		self.irJURA=self.createInput('ir2')
		self.timerJURA=Impulse(120)

		self.irROUTE=self.createInput('ir3')
		self.timerROUTE=Impulse(120)

		self.ccuError=self.createInput('ccuerr')
		self.timerCCUError=Impulse(900)

		self.job(self.ccuThread)

	def onRun(self):
		if self.chenillard.isActive():
			for item in self.chenillard.items():
				if item==self.chenillard.itemActive():
					item.value=1
				else:
					item.value=0
		else:
			if self.intrusion.value:
				self.lightFHE.value=1
				self.lightFHE_DCH.value=1
				self.lightDCH.value=1
				self.lightKITCHEN.value=1
				self.lightENTRANCE.value=1
				self.lightCONFERENCE.value=1
			else:
				self.lightFHE.value=self.timerSALEVE.value or self.timerROUTE.value
				self.lightFHE_DCH.value=self.timerSALEVE.value or self.timerVOIRONS.value
				self.lightDCH.value=self.timerSALEVE.value or self.timerVOIRONS.value
				self.lightKITCHEN.value=self.timerVOIRONS.value or self.timerJURA.value
				self.lightENTRANCE.value=self.timerVOIRONS.value or self.timerJURA.value or self.timerROUTE.value
				self.lightCONFERENCE.value=self.timerSALEVE.value or self.timerROUTE.value

		self.ccuError=self.timerCCUError.value

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
						if notification.isSource('JEQ0701998:1'):   	# kitchen
							self.timerVOIRONS.pulse()
							self.timerJURA.pulse()
						elif notification.isSource('JEQ0701960:1'): 	# entree parking salle de conference
							self.timerSALEVE.pulse()
							self.timerROUTE.pulse()
						elif notification.isSource('JEQ0701645:1'): 	# parking FHE
							self.timerSALEVE.pulse()
							self.timerROUTE.pulse()
						elif notification.isSource('JEQ0701644:1'): 	# parking saleve
							self.timerSALEVE.pulse()
							self.timerVOIRONS.pulse()
							self.timerROUTE.pulse()
						elif notification.isSource('JEQ0701577:1'): 	# parking voirons
							self.timerVOIRONS.pulse()
							self.timerSALEVE.pulse()
						elif notification.isSource('KEQ0194126:1'): 	# parking jura
							self.timerJURA.pulse()
							self.timerROUTE.pulse()
							self.timerVOIRONS.pulse()
					elif notification.key=='error' or notification.key=='sticky_unreach':
						if notification.value:
							ccu.logger.error(notification)
							self.timerCCUError.pulse()
						else:
							ccu.logger.debug(notification)
					else:
						ccu.logger.debug(notification)
				except:
					ccu.logger.error("exception occured while processing ccu event")
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
