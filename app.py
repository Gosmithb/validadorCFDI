import os
from pathlib import Path
import time
import tkinter as tk
from tkinter import filedialog
from lxml import etree
import requests
import shutil

root = tk.Tk()
root.withdraw()  # Oculta la ventana principal
parser = etree.XMLParser()

API_URL = "https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc"

def leer_cfdi_lxml(path_xml):
  ns = {
    'cfdi': 'http://www.sat.gob.mx/cfd/4',
    'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'
  }

  tree = etree.parse(path_xml, parser)

  root = tree.getroot()
  total = root.attrib.get("Total")
  sello = root.attrib.get("Sello")
  emisor = root.find("cfdi:Emisor", namespaces=ns).attrib.get("Rfc")
  receptor = root.find("cfdi:Receptor", namespaces=ns).attrib.get("Rfc")
  uuid = root.find(".//tfd:TimbreFiscalDigital", namespaces=ns).attrib.get("UUID")
  return {"uuid": uuid, "emisor": emisor, "receptor": receptor, "total": total, "sello": sello[-8:]}

def validar_cfdi(uuid, rfc_emisor, rfc_receptor, total, sello):
  
  params = {
    "re": rfc_emisor,
    "rr": rfc_receptor,
    "tt": total,
    "id": uuid,
    "fe": sello
  }

  headers = {
    "Content-Type": 'text/xml;charset="utf-8"',
    "Accept": "text/xml",
    "SOAPAction": "http://tempuri.org/IConsultaCFDIService/Consulta"
  }

  xml_body = """<?xml version="1.0" encoding="utf-8"?>
  <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
    <soapenv:Header/>
    <soapenv:Body>
      <tem:Consulta>
        <tem:expresionImpresa>
          <![CDATA[?re={re}&rr={rr}&tt={tt}&id={id}&fe={fe}]]>
        </tem:expresionImpresa>
      </tem:Consulta>
    </soapenv:Body>
  </soapenv:Envelope>""".format(**params)

  # response = requests.get(full_url, headers=headers)
  response = requests.post(API_URL, data=xml_body.encode('utf-8'), headers=headers)
  
  return etree.fromstring(response.content, parser)

def main():
  print("Iniciando la aplicación...")
  rutaOrigen = filedialog.askdirectory(title="Selecciona la carpeta de origen")
  if not rutaOrigen:
    print("No se seleccionó ninguna carpeta de origen. Saliendo...")
    return
  
  rutaDestino = filedialog.askdirectory(title="Selecciona la carpeta de destino")
  if not rutaDestino:
    print("No se seleccionó ninguna carpeta de destino. Saliendo...")
    return

  for root, _, files in os.walk(rutaOrigen):
    for file in files:
      if file.endswith('.xml'):
        print(f"Procesando archivo: {file}")
        path_xml = Path(root) / file

        if not path_xml.is_file():
          print(f"El archivo {file} no es un archivo válido. Omitiendo...")
          continue
        
        # Leer el CFDI usando lxml
        datosCFDI = leer_cfdi_lxml(path_xml)

        if datosCFDI:
          respuestaCFDI = validar_cfdi(
              datosCFDI["uuid"], 
              datosCFDI["emisor"], 
              datosCFDI["receptor"], 
              datosCFDI["total"], 
              datosCFDI["sello"]
            )
          
          ns = {
            's': 'http://schemas.xmlsoap.org/soap/envelope/',
            'temp': 'http://tempuri.org/',
            'a': 'http://schemas.datacontract.org/2004/07/Sat.Cfdi.Negocio.ConsultaCfdi.Servicio'
          }

          codigo_estatus = respuestaCFDI.xpath('//a:CodigoEstatus/text()', namespaces=ns)
          estado = respuestaCFDI.xpath('//a:Estado/text()', namespaces=ns)
          es_cancelable = respuestaCFDI.xpath('//a:EsCancelable/text()', namespaces=ns)
          estatus_cancelacion = respuestaCFDI.xpath('//a:EstatusCancelacion/text()', namespaces=ns)
          validacion_efos = respuestaCFDI.xpath('//a:ValidacionEFOS/text()', namespaces=ns)

          if estado is None or not estado:
            print(f"El CFDI {datosCFDI['uuid']} no se encontró o no es válido.")
            continue 

        #   if estado[0] in ["Vigente", "Cancelado"]:
        #     subcarpeta = estado[0]
        #   else:
        #     subcarpeta = "Error"

        #   destino_path = Path(rutaDestino) / subcarpeta / file
        #   destino_path.parent.mkdir(parents=True, exist_ok=True)
        #   shutil.copy2(path_xml, destino_path)

        if estado[0] == "Cancelado":
            destino_path = Path(rutaDestino) / estado[0] / file
            destino_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(path_xml, destino_path)

        elif estado[0] == "Vigente":
            destino_path = Path(rutaDestino) / estado[0] / file
            destino_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(path_xml, destino_path)

        else:
            subcarpeta = "Error"
            destino_path = Path(rutaDestino) / subcarpeta / file
            destino_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(path_xml, destino_path)

        with open("archivos_procesados.txt", 'a', encoding='utf-8') as log_file:
            log_file.write(f"{file}: {estado[0]}\n")

        time.sleep(18) #36 segundos = 100 requests por hora

if __name__ == "__main__":
    main()