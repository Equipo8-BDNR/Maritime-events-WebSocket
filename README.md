# Proyecto de Procesamiento en Tiempo Real: Maritime AIS Stream

## 1. Enlaces a las APIs y Documentación
* **Sitio oficial / Documentación de API:** [https://aisstream.io](https://aisstream.io)
* **Documentación WebSocket:** [https://aisstream.io/documentation](https://aisstream.io/documentation)
* **APIs del Stream:** [https://aisstream.io/account)](https://aisstream.io/account)

## 2. Descripción del Stream de Datos

### Resumen
El stream produce transmisiones en tiempo real de la localización y otros datos de embarcaciones a nivel global mediante el protocolo WebSocket. Incluye alertas e información de identificación de buques (MMSI, nombre, tipo de navío), posición geográfica (latitud, longitud), estado de navegación, velocidad (SOG), rumbo (COG), destino y tiempo estimado de llegada (ETA).

### Origen y Autoría
El stream es operado por la plataforma **AISStream.io**, la cual agrega datos transmitidos por transceptores **AIS (Automatic Identification System)** de barcos, capturados por estaciones base terrestres y receptores satelitales a nivel mundial.

### Diccionario de Datos
En el stream hay 25 tipos de mensaje JSON todos estos tienen las etiquetas "MessageType", "Metadata" y "Message". No todos son de eventos maritimos, algunos son respuestas del sistema estos no contienen la información de la embarcación dentro de *Metadata*.

* *MessageType:* Esta nos dice el tipo de mensaje que contiene el JSON.
* *Metadata:* Se encuentra la identidad básica del barco y la posición global.
* *Message:* Son los datos específicos del tipo de mensaje (se eligen de acuerdo con el MessageType).

A continuación se presenta un ejemplo de la estructura del mensaje con MessageType *PositionReport*

```bash
{
  "MessageType": "PositionReport", // Tipo de evento 

  "MetaData": // Datos generales de la embarcación
  { 
    "MMSI": 235092800,             // Numérico (Entero): Identificador único de 9 dígitos de la embarcación
    "ShipName": "OCEAN VOYAGER",    // Texto Libre: Nombre registrado del buque
    "latitude": 25.7617,           // Numérico (Flotante): Latitud en grados decimales (-90 a 90)
    "longitude": -80.1918,         // Numérico (Flotante): Longitud en grados decimales (-180 a 180)
    "time_utc": "2026-10-10T14:30:00Z" // Serie Temporal: Fecha/hora UTC de recepción del reporte
  },

  "Message": 
  {
    "PositionReport": 
    {
      "Sog": 12.4,                 // Numérico (Flotante): Speed Over Ground / Velocidad en nudos
      "Cog": 185.2,                // Numérico (Flotante): Course Over Ground / Rumbo en grados (0-359.9)
      "TrueHeading": 186,          // Numérico (Entero): Dirección real de proa (511 = No disponible)
      "NavigationalStatus": 0      // Categoría/Cualitativo: Estado (ej. 0 = Bajo motor, 1 = Fondeado)
    }
  }
}
```
### Catálogo de Tipos de Mensajes de AIS Stream
Se enlistan los tipos de mensajes y una descripción, se tomó en cuenta la división que presenta el stream para hacer la lista.

#### Envelope (Control y Suscripción)
Mensajes orientados a la gestión del protocolo de conexión WebSocket y notificaciones administrativas del sistema.

* **`AisStreamMessage`**: Objeto contenedor principal (*wrapper*) que encapsula cualquier evento proveniente del stream de datos.
* **`SubscriptionMessage`**: Mensaje de configuración enviado por el cliente para suscribirse a filtros específicos (áreas geográficas o MMSIs).
* **`SubscriptionConfirmation`**: Notificación del servidor que confirma la activación de la suscripción y valida si la compresión (`CompressionEnabled`) está activa.
* **`SubscriptionConfirmationMessage`**: Contenedor envolvente enviado por la API tras procesar una solicitud de suscripción.

#### Position (Telemetría de Posición)
Mensajes de geolocalización e indicadores dinámicos de movimiento de embarcaciones y estaciones terrestres.

* **`PositionReport`**: Reportes dinámicos principales de la nave (Mensajes AIS 1, 2 y 3). Transmite latitud, longitud, velocidad sobre el fondo (`Sog`), rumbo (`Cog`), proa (`TrueHeading`) y estado operacional (`NavigationalStatus`).
* **`BaseStationReport`**: Reporte transmitido por estaciones base en tierra (Mensaje AIS 4). Indica la posición geográfica exacta del receptor terrestre y la marca de tiempo sincrónica.
* **`StandardClassBPositionReport`**: Reporte simplificado de posición emitido por embarcaciones más pequeñas o de recreo que utilizan equipamiento AIS Clase B (Mensaje AIS 18).
* **`ExtendedClassBPositionReport`**: Reporte extendido para Clase B que añade características adicionales del barco a los datos de posición (Mensaje AIS 19).
* **`StandardSearchAndRescueAircraftReport`**: Reporte de posición emitido por aeronaves dedicadas a misiones de Búsqueda y Rescate (SAR / Mensaje AIS 9).
* **`AidsToNavigationReport`**: Información enviada por balizas, faros o boyas de señalización (AtoN / Mensaje AIS 21), indicando su ubicación y estado.

#### Static and Voyage (Datos del Buque y Travesía)
Información administrativa, física y logística sobre la embarcación y su ruta comercial.

* **`ShipStaticData`**: Datos estáticos y de travesía del buque (Mensaje AIS 5). Contiene el nombre del barco (`ShipName`), número IMO, tipo de nave (`Type`), dimensiones físicas (`Dimension`), puerto de destino (`Destination`) y tiempo estimado de llegada (`Eta`).
* **`DataLinkManagementMessage`**: Datos técnicos de asignación e intercalado de franjas horarias de radio (Slots TDMA / Mensaje AIS 20) para el mantenimiento del enlace de datos marítimo.
* **`GroupAssignmentCommand`**: Instrucciones enviadas a un grupo de barcos para definir sus intervalos de transmisión o frecuencias (Mensaje AIS 23).
* **`StaticDataReport`**: Reporte en dos partes que transmite los metadatos estáticos de embarcaciones con transceptores Clase B (Mensaje AIS 24).

#### Binary Data (Cargas Útiles de Datos Binarios)
Mensajes orientados a la transmisión de datos personalizados o estructurados entre estaciones.

* **`AddressedBinaryMessage`**: Transmisión de datos binarios dirigida a una embarcación o estación específica por su MMSI (Mensaje AIS 6).
* **`BinaryAcknowledge`**: Acuse de recibo de la recepción exitosa de un mensaje binario previo direccionado (Mensaje AIS 7).
* **`BinaryBroadcastMessage`**: Emisión generalizada de datos binarios difundida a todas las estaciones en rango (Mensaje AIS 8).
* **`SingleSlotBinaryMessage`**: Mensaje binario compacto de longitud reducida enviado en un solo segmento de tiempo (Mensaje AIS 25).
* **`MultiSlotBinaryMessage`**: Mensaje binario extenso enviado a través de múltiples segmentos de tiempo consecutivos (Mensaje AIS 26).

#### Network and Control (Gestión de Red y Canales)
Comandos del sistema para la gestión del espectro radioeléctrico y asignación de frecuencias.

* **`Interrogation`**: Solicitud enviada por una estación base o barco para requerir datos específicos a otra nave (Mensaje AIS 10).
* **`ChannelManagement`**: Instrucciones para cambiar de canal de transmisión de radiofrecuencia VHF dentro de una zona geográfica definida (Mensaje AIS 22).

#### Safety (Seguridad y Alertas)
Alertas críticas, acuses de recibo y comunicaciones de emergencia marítima.

* **`AddressedSafetyRelatedMessage`**: Notificación de seguridad dirigida específicamente a un receptor en particular (Mensaje AIS 12).
* **`SafetyRelatedAcknowledge`**: Acuse de recibo que confirma la lectura de un mensaje de seguridad direccionado (Mensaje AIS 13).
* **`SafetyRelatedBroadcastMessage`**: Alerta o aviso de seguridad marítima emitido en abierto a todos los barcos en la zona (Mensaje AIS 14).
* **`LongRangeAisBroadcastMessage`**: Datos de posición y estado optimizados para ser capturados por satélites u otros sistemas de largo alcance (Mensaje AIS 27).


### Clasificación de Variables
Se presentan algunas de las variables que podemos encontrar dentro de los *Message* y *Metadata*.

* **Variables Cuantitativas:**
  * `latitude`, `longitude` (Coordenadas geográficas).
  * `Sog` (Velocidad en nudos).
  * `Cog`, `TrueHeading` (Ángulos de dirección/rumbo).
  * `Dimension.A`, `Dimension.B`, `Dimension.C`, `Dimension.D` (Dimensiones físicas de la nave en metros).
  * `Draught` (Calado del barco).

* **Variables Cualitativas:**
  * `MessageType` (Tipo de evento).
  * `NavigationalStatus` (Estado de navegación).
  * `ShipType` / `Type` (Categoría de buque).
  * `CargoType` (Tipo de carga declarada).

* **Texto No Estructurado:**
  * `ShipName` (Nombre comercial o registrado).
  * `Destination` (Destino en texto abierto ingresado por la tripulación; suele contener tipografía errónea o abreviaturas no estandarizadas).
  * `CallSign` (Indicativo de llamada de radio).

* **Series Temporales:**
  * `time_utc` / `Timestamp` (Marca de tiempo en milisegundos o ISO-8601 que registra exactamente cuándo ocurrió o se procesó la posición).

### Consideraciones Éticas y Privacidad

* **Sensibilidad de la Información:** Aunque los datos AIS son de difusión pública por seguridad marítima mundial (IMO/OMI), el monitoreo continuo de embarcaciones pesqueras o recreativas en tiempo real puede exponer patrones de trabajo o ubicaciones sensibles. También podrían presentan riesgos de seguridad si no se gestionan adecuadamente los controles de acceso a los paneles analíticos

* **Calidad y Sesgo:** El campo `Destination` y otros campos son ingresados manualmente por operadores humanos, lo que introduce errores de tipeo y campos nulos.

