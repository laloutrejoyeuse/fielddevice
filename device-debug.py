#!/usr/bin/python
from device import Device, IOManager
import time
import logging

class MyIOManager(IOManager):
	def onInit(self):

		# create inputs
		self.li0=self.createInput('li0', 'bouton 0 carte piface (trigger lorsque down)')
		self.li0.setRunModeAsRaisingEdgeCounter()
		self.li1=self.createInput('li1', 'bouton 1 carte piface (trigger lorsque impulsion 0->1->0)')
		self.li1.setRunModeAsImpulseCounter()
		self.li2=self.createInput('li2', 'bouton 2 carte piface (trigger a chaque changement up<-->down)')
		self.li2.setRunModeAsEdgeCounter()
		self.li3=self.createInput('li3', 'bouton 3 carte piface')

		# create outputs
		self.lo0=self.createOutput('lo0', 'relai 0 piface')
		self.lo1=self.createOutput('lo1', 'image du bouton general chambre de pierre')

		self.lo0.value=1

		self.periodicTimer(3, self.onTimerToggle)

		self.job(self.piCamThread)

	def piCamThread(self):
		i=5
		while not self.isStopRequest() and i>0:
			self.logger.debug("PICAM%d!" % i)
			i-=1
			time.sleep(1)

	def onRun(self):
		# process inputs

		# process outputs
		for io in self.inputs():
			if io.checkAndClearTrigger():
				self.lo0.toggle()

		if self.li3.value:
			self.lo0.toggle()

		# keep CPU load as low as possible
		self.sleep(0.01)

	def onTimerToggle(self):
		self.lo0.toggle()

	def onUpdateOutput(self, io):
		self.logger.debug("onUpdateOutput(%s)->%f" % (io.name, io.value))

	def onStop(self):
		# do a clean exit
		self.resetAllOutputs()

	def onRelease(self):
		pass
	

dev=Device('https://splustdata.dyndns.org/rws/api/dcf', 
	's_STDEMO_fd2', 'BFEBB90A6F1876531F14225D6AAF3BE0', 
	MyIOManager, 
	'localhost', logging.DEBUG)

dev.addFileToScriptUpdateMonitor(__file__)
dev.enableShutdownOnScriptUpdate()

dev.start()

