#!/usr/bin/python
# coding: utf-8

import sys
import subprocess
import os
from lxml import etree
import time
import logging

#Depuracion
logging.basicConfig(level = logging.DEBUG) #.DEBUG para debug .INFO lo oculta
logger = logging.getLogger('pfinalp1')


#Menu ayuda
ayuda = """Uso: pfinal.py [OPCIÓN...] [MÁQUINA] 

  crear [Numero_maquinas],   	Crea el numero de maquinas a utilizar en el escenario, si esta opción no se incluye se crearan solamente 2 maquinas.
  arrancar [Maquina_arrancar],  Máquinas o maquina que se van a arrancar, si no se pone ningún parametro opcional con el nombre de la máquina se arrancarán todas.
  parar [Maquina_parar],  	Máquinas o maquina que se va a parar, si no se pone ningún parametro opcional con el nombre de la máquina se pararán todas.
  balanceador,                  Lanza el ping para probrar la funcionalidad del balanceador de carga
  monitor,  			Muestra el estado de las máquinas del escenario (Running, Shut Down).
  memoria Nombre_Maquina,       Lanza el comando top sobre las maquinas virtuales para ver el estado de la memoria.
  dominfo Nombre_Maquina,			Muestra el estado del dominio seleccionado.
  destruir,			Para y borra todo el escenario y elimina cualquier archivo dependiente de las maquinas virtuales.
  
Los argumentos obligatorios no van entre corchetes mientras que los opcionales que van entre corchetes se pueden omitir.

Informe de los errores a a.molinas@alumnos.upm.es o javier.conde.diaz@alumnos.upm.es  """


class E(RuntimeError):
	def __init__(self, msg):
		self.msg = msg
	def getMsg(self):
		return self.msg

#Numero de servidores
def leer():
	f1 = open("servidores", "r")
	for line in f1:
		numero = line
		numero.strip()
		f1.close()
		return int(numero)

def guardar(arrancados):
	f2 = open("arrancados","w")
	for x in arrancados:
		f2.write(x + "\n")
	f2.close()
	logger.debug(arrancados)


# Estado servidores (apagado, encendido)
def leerarrancado():
	arrancado=[]
	f2 = open("arrancados","r")
	for line in f2:
		servidor = line
		servidor= servidor.strip('\n')
		arrancado.append(servidor)
	f2.close()	
	
	return (arrancado)
		
#Array con el nombre de todas las MV
def obtenerArrayMaquinas():
	servers = leer()
	maquinas = ["c1" , "lb"]
	for x in range (1, servers + 1):
		maquina = "s" + str(x)
		maquinas.append(maquina)
	return maquinas
	
def crear():
	#Creo el fichero donde pongo el estado de las maquinas
	f2 = open("arrancados" , "w")
	f2.close()
	#Creo las imagenes de diferencias
	servers = leer() #Numero de servidores
	maquinas = obtenerArrayMaquinas() #Array con el nombre de todas las MV
	rutaFichero = os.getcwd()
	comprimida=os.path.isfile(rutaFichero+"/cdps-vm-base-p3.qcow2.bz2") #Voy a comprobar si la maquina esta comprimida
	#Aqui hago las sentencias para la descompresion del archivo
	if comprimida == True:
		subprocess.call('bunzip2 cdps-vm-base-p3.qcow2.bz2', shell = True)
	for x in maquinas:
		subprocess.call('qemu-img create -f qcow2 -b cdps-vm-base-p3.qcow2 ' + x + '.qcow2', shell = True)
		
	#Modifico los xml
	
	for x in maquinas:
		tree = etree.parse('plantilla-vm-p3.xml')
		root = tree.getroot()
		nombre = root.find("name")
		nombre.text = x
		

		source = root.find("./devices/disk[@type='file'][@device='disk']/source")
		source.set("file", rutaFichero + "/" + x + ".qcow2")

		bridge = root.find("./devices/interface[@type='bridge']/source")
		LAN = "LAN1"
		if x == "c1":
			LAN = "LAN1"
		elif x == "lb":
			root[10].insert(3, etree.Element("interface"))
			root[10][3].set("type" , "bridge")
			root[10][3].insert(0, etree.Element("source"))
			root[10][3].insert(1, etree.Element("model"))
			root[10][3][0].set("bridge", "LAN2")
			root[10][3][1].set("type", "virtio")

			LAN = "LAN1"
		else:
			LAN = "LAN2"

		bridge.set("bridge", LAN)
		
		f1 = open(x + '.xml' , "w")
		f1.write(etree.tostring(tree))
		f1.close()

	#Creo los bridges
	
	subprocess.call('sudo brctl addbr LAN1', shell = True)
	subprocess.call('sudo brctl addbr LAN2', shell = True)
	subprocess.call('sudo ifconfig LAN1 up', shell = True)
	subprocess.call('sudo ifconfig LAN2 up', shell = True)
		
	#Creo las MV de forma persistente
	for x in maquinas:
		subprocess.call('virsh define ' + x + '.xml', shell = True)

	#Configuro los archivos de redes, nombre de la maquina y LB como router
		#Ips de las interfaces eth0 de las MV y gateways
	subprocess.call('mkdir mnt', shell = True)
	ip = ["10.0.1.2", "10.0.1.1"]
	gateway = ["10.0.1.1", "no tiene"]
	for x in range(1, servers + 1):
		ip.append("10.0.2." + str(10 + x))
		gateway.append("10.0.2.1")
	
		#cambio el contendio de los archivos
		
	for x in range(0, len(maquinas)):
		logger.debug(maquinas[x])
		
		subprocess.call("sudo vnx_mount_rootfs -s -r " + maquinas[x] +".qcow2 mnt", shell = True)
		f1 = open("mnt/etc/hostname", "w")
		f1.write(maquinas[x])
		f1.close()
		finterface = open("mnt/etc/network/interfaces" , "w")
		finterface.write("auto lo" + "\n")
		finterface.write("iface lo inet loopback" + "\n")
		finterface.write("auto eth0" + "\n")
		finterface.write("iface eth0 inet static" + "\n")
		finterface.write("address " + ip[x] + "\n")
		finterface.write("netmask 255.255.255.0" + "\n")
		if maquinas[x] != "lb":
			finterface.write("gateway " + gateway[x] + "\n")
			finterface.close()
		#Configuracion del router cambia un poco, debo anadirle interfaz eth1
		else:
			finterface.write("auto eth1" + "\n")
			finterface.write("iface eth1 inet static" + "\n")
			finterface.write("address 10.0.2.1 " + "\n")
			finterface.write("netmask 255.255.255.0" + "\n")
			finterface.close()
			#Configuro el balanceador
			fbalancr = open("mnt/etc/rc.local", 'r')
			lines = fbalancr.readlines()
			fbalancr.close()
			fbalancw = open("mnt/etc/rc.local", 'w')
			balanceador = "xr -dr --verbose --server tcp:0:8080 "
			for x in range(2, len(maquinas)):
				balanceador += "--backend " + ip[x] + ":80 "
			balanceador += "--web-interface 0:8001"
			for line in lines:
				if "exit 0" in line:
					fbalancw.write("service apache2 stop" + "\n")
					fbalancw.write(balanceador + " \n" )
					fbalancw.write(line)
				else:
					fbalancw.write(line)
			fbalancw.close()
			#Configuro para que se comporte como router ip
			f2 = open('mnt/etc/sysctl.conf', 'r')
			lines = f2.readlines()
			f2.close()
			f3 = open('mnt/etc/sysctl.conf', 'w')
			for line in lines:
				if "net.ipv4.ip_forward" in line:
					f3.write("net.ipv4.ip_forward=1")
				else:
					f3.write(line)
			f3.close()
			
		
		subprocess.call("bash -c \"echo "+maquinas[x]+" > ./mnt/var/www/html/index.html\" ", shell = True)
		time.sleep(1)				#no deberia de tener que usar el timer !!!!CAMBIAR
		subprocess.call('sudo vnx_mount_rootfs -u mnt', shell = True)
	subprocess.call('rm -r mnt/', shell = True)
	#Configuro el host
	subprocess.call('sudo ifconfig LAN1 10.0.1.3/24', shell = True)
	subprocess.call('sudo ip route add 10.0.0.0/16 via 10.0.1.1', shell = True)

def arrancar(machines):
	arrancados=[]
	arrancados = leerarrancado()
	servers = leer()
	if machines == "todas":
		maquinas = obtenerArrayMaquinas()
	else:
		maquinas = [machines]
		if not machines in obtenerArrayMaquinas() :
			logger.debug("Lo sentimos, esa maquina no esta en elsecenario")
			return
	for x in maquinas:
		if not x in arrancados:
		
			subprocess.call('virsh start ' + x, shell = True)
			#arranco en background --> &
			subprocess.call('xterm -e " virsh console ' + x + '" &', shell = True)
			arrancados.append(x);
	guardar(arrancados)		
	

def parar(machines):
	arrancados=[]
	arrancados = leerarrancado()
	servers = leer()
	if machines == "todas":
		maquinas = obtenerArrayMaquinas()
	else:
		maquinas = [machines]
		if not machines in obtenerArrayMaquinas() :
			logger.debug("Lo sentimos, esa maquina no esta en elsecenario") 
			return
	for x in maquinas:
		if x in arrancados:

			subprocess.call('virsh shutdown ' + x, shell = True)
			arrancados.remove(x);
	guardar(arrancados)

def destruir():
	arrancados=[]
	arrancados = leerarrancado()
	servers = leer()
	maquinas = obtenerArrayMaquinas()
	for x in maquinas:		
		if x in arrancados:		
			subprocess.call('virsh destroy ' + x, shell = True)	
			arrancados.remove(x)
		subprocess.call('virsh undefine ' + x, shell = True)
		subprocess.call('rm ' + x + '.xml', shell = True)
		subprocess.call('rm -f ' + x + '.qcow2', shell = True)
		
		
	subprocess.call('rm servidores', shell = True)
	subprocess.call('rm arrancados', shell = True)
			
#No se si tengo que descomprimirlo o ya me lo dan
#bunzip2 cdps-vm-base-p3.qcow2.bz2 .

if len(sys.argv) > 1:
	orden = sys.argv[1]
	if orden == "crear":
		servers = 2
		if len (sys.argv) > 2:
			servers = int(sys.argv[2])
		if servers < 1 or servers > 5: 
			try:
				raise E("Error, Numero de servidores entre 1 y 5")
			except E, obj:
				logger.debug('Msg:'+ obj.getMsg())
			sys.exit(1)
		else:
			f1 = open("servidores" , "w")
			f1.write(str(servers))
			f1.close()
			crear()
			


	elif orden == "arrancar":
		if len(sys.argv) == 2:
			arrancar("todas")
		elif len(sys.argv) == 3:
			arrancar(sys.argv[2])
		
			

		else:
			print ayuda

	elif orden == "parar":
		if len(sys.argv) == 2:
			parar("todas")
		elif len(sys.argv) == 3:
			parar(sys.argv[2])		
		
		else:
			print ayuda

	elif orden == "destruir":
		 destruir()
	elif orden == "monitor":
		subprocess.call('xterm -e "watch --interval 5 virsh list ' + '" &', shell = True)
	elif orden == "memoria":
		if len(sys.argv) == 3:
			servers = leer()
			maquinas = obtenerArrayMaquinas()
			monitorizar= sys.argv[2]
			variable = False
			iteracion = 0
			for x in maquinas:
				ip = ["10.0.1.2", "10.0.1.1"]
				for x in range(1, servers + 1):
					ip.append("10.0.2." + str(10 + x))
			for x in maquinas:
				variable = ( monitorizar ==x)
				if variable: 
					subprocess.call('xterm -e "watch  ssh root@'+ ip[iteracion]+' \'top -b | head -n 20\' '+'"&', shell = True)
					break; #para salir del for
					
				iteracion += 1
				logger.debug(iteracion)
			if ( variable != True):
				print(" Lo sentimos, la maquina que ha intentado monitorizar no se encuentra en el escenario")
		else:
			print ayuda

	elif orden == "dominfo":
		if len(sys.argv) == 3:
			servers = leer()
			maquinas = obtenerArrayMaquinas()
			monitorizar= sys.argv[2]
			variable = False
			iteracion = 0
			for x in maquinas:
				variable = ( monitorizar ==x)
				if variable: 
					subprocess.call('xterm -e "watch virsh dominfo '+ monitorizar+'"&', shell = True)
					break; #para salir del for
					
				iteracion += 1
				logger.debug(iteracion)
			if ( variable != True):
				print(" Lo sentimos, la maquina sobre la que ha intentado lanzar este comando no se encuentra en el escenario")
		else:
			print " Por favor este parametro necesita un parametro OPCIONAL con el nombre de la maquina de la que quieres obtener su info de dominio"


				
	elif orden == "balanceador":	
	
		subprocess.call('xterm -e " while true; do curl 10.0.1.1:8080; sleep 0.1; done" &', shell = True)
					
	
	else: 
		print ayuda
else:
	print ayuda
	









