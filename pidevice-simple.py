#!/usr/bin/python
from device import Device, IOManager
from pifacedigitalio import PiFaceDigital

class MyIOManager(IOManager):
	def onInit(self):
		self.pf=PiFaceDigital()

		# create inputs
		self.li0=self.createInput('li0', 'bouton 0 carte piface (trigger lorsque down)')
		self.li0.setRunModeAsRaisingEdgeCounter()
		self.li1=self.createInput('li1', 'bouton 1 carte piface (trigger lorsque impulsion 0->1->0)')
		self.li1.setRunModeAsImpulseCounter()
		self.li2=self.createInput('li2', 'bouton 2 carte piface (trigger a chaque changement up<-->down)')
		self.li2.setRunModeAsEdgeCounter()

		# create outputs
		self.lo0=self.createOutput('lo0', 'relai 0 piface')

	def onRun(self):
		# process inputs
		self.li0.value=self.pf.input_pins[0].value
		self.li1.value=self.pf.input_pins[1].value
		self.li2.value=self.pf.input_pins[2].value

		# process outputs
		for io in self.inputs():
			if io.checkAndClearTrigger():
				self.lo0.toggle()

		# keep CPU load as low as possible
		self.sleep(0.01)

	def onUpdateOutput(self, io):
		print "onUpdateOutput(%s)->%f" % (io.name, io.value)
		if io==self.lo0:
			self.pf.output_pins[0].value=io.value

	def onStop(self):
		# do a clean exit
		self.resetAllOutputs()

	def onRelease(self):
		pass
	

dev=Device(MyIOManager, 8888)
dev.allowRemoteShutdown(True)
dev.start()

