import xmlrpclib
from SimpleXMLRPCServer import SimpleXMLRPCServer
import socket
from Queue import Queue
from threading import Thread
from threading import Event
import urlparse
import sys, logging, logging.handlers


# Warning : slow request could be due to dns resolving. 
# Adding hosts to /etc/hosts boost seriously the things ;)
# http://stackoverflow.com/questions/14504450/pythons-xmlrpc-extremely-slow-one-second-per-call
# http://www.answermysearches.com/xmlrpc-server-slow-in-python-how-to-fix/2140/

# CCU API 
# https://groups.google.com/group/openhab/attach/a3f975a94f9e9b28/HM_XML-RPC_V1_502.pdf
# Chapter 5

class CCUEventHandler:
	def __init__(self, ccu):
		self._ccu=ccu

	def event(self, interface, address, key, value):
		self._ccu.onEvent(interface, address, key, value)
		return ''

	def listDevices(self, *args):
		# print ">LISTDEVICES"
		# for arg in args:
		# 	print arg
		# 	print "---"
		return ''

	def newDevices(self, interface, devices):
		# print ">NEWDEVICES"
		# for device in devices:
		# 	print device
		# 	print "---"
		return ''

	def newDevice(self, *args):
		#print ">NEWDEVICE"
		# for arg in args:
		# 	print arg
		return ''

	def shutdown(self, *args):
		self._ccu._eventShutdown.set()
		return ''



class Notification(object):
	def __init__(self, domain, source, name, data={}):
		self._domain=domain
		self._source=source
		self._name=name
		self._data=data

	@property
	def domain(self):
	    return self._domain

	@property
	def source(self):
	    return self._source

	def isSource(self, sources):
		try:
			if not isinstance(sources, (list, tuple)):
				sources=[sources]
			for source in sources:
				if source.lower()==self.source.lower():
					return True
		except:
			pass
		return False

	@property
	def name(self):
	    return self._name

	@property
	def key(self):
		try:
			return self._data['key']
		except:
			pass

	@property
	def value(self):
		try:
			return self._data['value']
		except:
			pass

	def __getitem__(self, key):
		try:
			return self._data[key]
		except:
			pass

	def __setitem__(self, key, item):
		self._data[key]=item

	def dump(self):
		return 'NOTIFICATION-%s/%s->%s(%s)' % (self.domain, self.source, self.name, self._data)

	def __repr__(self):
		return self.dump()

	def __str__(self):
		return self.dump()


class NotificationDispatcher(object):
	def __init__(self):
		self._queue=Queue()
		self._event=Event()
		self._eventClose=Event()

	def post(self, notification):
		if notification and not self._eventClose.isSet():
			self._queue.put(notification)
			self._event.set()

	def get(self):
		try:
			return self._queue.get(False)
		except:
			self._event.clear()
		return None

	def sleep(self, delay):
		if not self._eventClose.isSet():
			return self._event.wait(delay)

	def waitForNotification(self, delay):
		if self.sleep(delay):
			return self.get()

	def kill(self):
		self._eventClose.set()
		self._event.set()


class CCU:
	def __init__(self, name, urlCCU, urlEventServer, logger=None):
		if not logger:
			logger=logging.getLogger("CCU")
			logger.setLevel(logging.DEBUG)
			ch = logging.StreamHandler(sys.stdout)
			ch.setLevel(logging.DEBUG)
			formatter = logging.Formatter('%(asctime)s:%(name)s::%(levelname)s::%(message)s')
			ch.setFormatter(formatter)
			logger.addHandler(ch)
			logger.debug('test2')

		self._logger=logger
		self._notificationDispatcher=NotificationDispatcher()
		self._eventStop=Event()
		self._eventShutdown=Event()
		self._name=name
		self.logger.debug('creating XMLRPC client channel (%s)' % urlCCU)
		self._rpcClient=xmlrpclib.ServerProxy(urlCCU)

		url=urlparse.urlparse(urlEventServer)
		self._urlEventServer=urlEventServer
		self.logger.debug('creating XMLRPC server channel (%s)' % urlEventServer)
		self._rpcEventServer=SimpleXMLRPCServer(('', url.port), logRequests=False)
		self._rpcEventServer.register_instance(CCUEventHandler(self))
		self._rpcEventServer.register_multicall_functions()
		#self._rpcEventServer.register_introspection_functions()

	@property
	def logger(self):
	    return self._logger

	def notify(self, source, name, data):
	 	self._notificationDispatcher.post(Notification('ccu', source, name, data))

	def onEvent(self, interface, address, key, value):
		#self.logger.debug("EVENT[%s](%s=%s)" % (address, key, value))
		try:
			self.notify(address.lower(), 'event', {'key':key.lower(), 'value':value})
		except:
			pass

	def waitForNotification(self, delay):
		return self._notificationDispatcher.waitForNotification(delay)

	def _registerEventServer(self):
		self.logger.debug('registering local events server with CCU')
		self._rpcClient.init(self._urlEventServer, self._name)	

	def _unregisterEventServer(self):
		self.logger.debug('unregistering local events server with CCU')
		self._rpcClient.init(self._urlEventServer)	

	def start(self):
		self._thread=Thread(target=self._manager)
		self._thread.start()
		self._registerEventServer()

	def stop(self):
		if not self._eventStop.isSet():
			self.logger.info('stop request!')
			self._eventStop.set()
			self._notificationDispatcher.kill()
			self._unregisterEventServer()
			try:
				# send a dummy request to force shutdown http server
				self.logger.debug('requesting local XMLRPC server shutdown...')
				url=urlparse.urlparse(self._urlEventServer)
				client=xmlrpclib.ServerProxy('http://127.0.0.1:%d' % url.port)
				client.shutdown()
			except:
				pass
			self.logger.info('waiting for XMLRPC server thread termination...')
			self._thread.join()
			self.logger.info('XMLRPC server halted')
	
	def _manager(self):
		self.logger.info('XMLRPC server started')
		while not self._eventShutdown.isSet():
			try:
				self._rpcEventServer.handle_request()
			except:
				pass


if __name__ == '__main__':
	import time
	ccu=CCU('myccu', 'http://192.168.0.29:2001', 'http://192.168.0.84:8077')
	ccu.start()
	try:
		n=ccu.waitForNotification(60)
		if n:
			print n.dump()
	except:
		pass
	ccu.stop()


	