fielddevice
===========

Digimat DCF FieldDevice Implementation


## Example 

Simple Device demo with the PiFaceDigital board (raspberry pi)

```
from device import Device, IOManager
from pifacedigitalio import PiFaceDigital

class MyIOManager(IOManager):
	def onInit(self):
		self.pf=PiFaceDigital()

		# create inputs
		self.i0=self.createInput('i0')
		self.i0.setRunModeAsRaisingEdgeCounter()

		# create outputs
		self.o0=self.createOutput('o0')
 
	def onRun(self):
		# process inputs
		self.i0.value=self.pf.input_pins[0].value

		# process outputs
		if self.i0.checkAndClearTrigger():
			self.o0.toggle()

		# keep CPU load as low as possible
		self.sleep(0.01)

	def onUpdateOutput(self, io):
		self.logger.debug("onUpdateOutput(%s)->%f" % (io.name, io.value))
		if io==self.o0:
			self.pf.output_pins[0].value=io.value

	def onStop(self):
		# do a clean exit
		self.resetAllOutputs()

	def onRelease(self):
		pass

	
dev=Device('https://192.168.2.1/rws/api/dcf', 
	's_STDEMO_fd2', 
	'BFEBB90A6F1876531F14225D6AAF3BE0', 
	MyIOManager)

dev.start()
```







