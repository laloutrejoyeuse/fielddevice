from device import Device, IOManager

class MyIOManager(IOManager):
	def onInit(self):
		#todo: create inputs
		#self.li0=self.createInput('li0', 'xxxxx')

		#todo: create outputs
		#self.lo0=self.createOutput('lo0', 'yyyyy')
		pass

	def onRun(self):
		#todo: process inputs values, or some of them @ each cycle (transfer output world into ios.value)
		#self.li0.value=...

		#todo: update outputs values (or some of them @ each cycle)
		#self.lo0.value=xxx+yyyy

		#cpu saver
		self.sleep(0.1)

	def onUpdateOutput(self, io):
		#todo: process the given output (apply io.value to the output world)
		#xxxx=io.value
		pass

	def onStop(self):
		# do a clean exit
		self.resetAllOutputs()

	def onRelease(self):
		pass

	def onTimeout(self, timer):
		#todo: process the given timer
		pass
	

dev=Device(MyIOManager, 8888)
dev.allowRemoteShutdown(True)
dev.start()
