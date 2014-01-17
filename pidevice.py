#!/usr/bin/python

from device import Device, IOManager
from pifacedigitalio import PiFaceDigital

class MyIOManager(IOManager):
	def onInit(self):
		self.pf=PiFaceDigital()

		self.li0=self.createInput('li0', 'bouton piface 0')
		self.li1=self.createInput('li1', 'bouton piface 1')

		self.li2=self.createInput('li2', 'bouton piface 2')
		self.li2.setRunModeAsRaisingEdgeCounter()

		self.li3=self.createInput('li3', 'bouton piface 3')
		self.li3.setRunModeAsEdgeCounter()

		self.lo0=self.createOutput('lo0', 'relai piface 0', 0)
		self.lo1=self.createOutput('lo1', 'relai piface 1', 1)

		self.lo1.value=1
		
		#self.timerWithHandler(5, self.onTimeoutToggle)

	def onRun(self):
		for io in [self.li0, self.li1, self.li2, self.li3]:
			io.value=self.pf.input_pins[io.index].value

		if self.li2.checkAndClearTrigger():
			self.lo1.toggle()

		self.sleep(0.01)

	def onUpdateOutput(self, io):
		print "onUpdateOutput(%s, %f):%s" % (io.name, io.value, io.label)
		if io in [self.lo0, self.lo1]:
			self.pf.output_pins[io.index].value=io.value

	# def onTimeout(self, timer):
	# 	print "onTimeout()"

	# def onTimeoutToggle(self, timer):
	# 	print "onTimeoutToggle()"
	# 	self.lo1.toggle()
	# 	timer.restart()

	def onStop(self):
		self.resetAllOutputs()

	def onRelease(self):
		pass
	

dev=Device(MyIOManager, 8888)
dev.allowRemoteShutdown(True)
dev.start()
