# Proyecto de Procesamiento en Tiempo Real: Maritime AIS Stream

## 1. Enlaces a las APIs y Documentación
* **Sitio oficial / Documentación de API:** [https://aisstream.io](https://aisstream.io)
* **Documentación WebSocket:** [https://aisstream.io/documentation](https://aisstream.io/documentation)
* **APIs del Stream (generación de API key):** [https://aisstream.io/account](https://aisstream.io/account)
* **Endpoint del stream:** `wss://stream.aisstream.io/v0/stream`

## 2. Descripción del Stream de Datos

### Resumen
El stream produce transmisiones en tiempo real de la localización y otros datos de embarcaciones a nivel global mediante el protocolo WebSocket. Incluye alertas e información de identificación de buques (MMSI, nombre, tipo de navío), posición geográfica (latitud, longitud), estado de navegación, velocidad (SOG), rumbo (COG), destino y tiempo estimado de llegada (ETA).

### Origen y Autoría
El stream es operado por la plataforma **AISStream.io**, la cual agrega datos transmitidos por transceptores **AIS (Automatic Identification System)** de barcos, capturados por estaciones base terrestres y receptores satelitales a nivel mundial.

### Diccionario de Datos
En el stream hay 25 tipos de mensaje JSON (los que se pueden pedir con `FilterMessageTypes`), todos estos tienen las etiquetas "MessageType", "MetaData" y "Message". No todos son de eventos maritimos, algunos son respuestas del sistema estos no contienen la información de la embarcación dentro de *MetaData*.

* *MessageType:* Esta nos dice el tipo de mensaje que contiene el JSON.
* *MetaData:* Se encuentra la identidad básica del barco y la posición global.
* *Message:* Son los datos específicos del tipo de mensaje (se eligen de acuerdo con el MessageType).

A continuación se presenta un ejemplo de la estructura del mensaje con MessageType *PositionReport*

```jsonc
{
  "MessageType": "PositionReport", // Tipo de evento 

  "MetaData": // Datos generales de la embarcación
  { 
    "MMSI": 311002056,             // Numérico (Entero): Identificador único de 9 dígitos de la embarcación
    "ShipName": "LEMANIA",    // Texto Libre: Nombre registrado del buque
    "latitude": 38.7398,           // Numérico (Flotante): Latitud en grados decimales (-90 a 90)
    "longitude": 14.81916,         // Numérico (Flotante): Longitud en grados decimales (-180 a 180)
    "time_utc": "2026-10-12 05:14:13.502595905 +0000 UTC" // Serie Temporal: Fecha/hora UTC de recepción del reporte
  },

  "Message": 
  {
    "PositionReport": 
    {
      "Sog": 10.4,                 // Numérico (Flotante): Speed Over Ground / Velocidad en nudos
      "Cog": 272.3,                // Numérico (Flotante): Course Over Ground / Rumbo en grados (0-359.9)
      "TrueHeading": 273,          // Numérico (Entero): Dirección real de proa (511 = No disponible)
      "NavigationalStatus": 0      // Categoría/Cualitativo: Estado (ej. 0 = Bajo motor, 1 = Fondeado)
    }
  }
}
```
> Ejemplo real capturado del stream (abreviado: el mensaje completo trae más campos). Los mensajes completos de `PositionReport` y `ShipStaticData` están en `samples/`.

#### Atributos de los mensajes capturados
La siguiente tabla define cada atributo de los dos tipos de mensaje con los que trabaja el proyecto (`PositionReport` y `ShipStaticData`) y de su `MetaData`. La columna *Clase* indica si es cuantitativa, cualitativa, texto no estructurado, temporal o identificador. Los rangos y frecuencias provienen de la captura de la sección 5. Los valores marcados como "no disponible" son valores centinela del estándar AIS y deben tratarse como nulos.

**`MetaData`** (viene en todos los mensajes de barcos)

| Atributo | Tipo | Clase | Significado | Valores especiales / observaciones |
|---|---|---|---|---|
| `MMSI` | Entero | Identificador | Maritime Mobile Service Identity: código de 9 dígitos que identifica al transmisor AIS. | Se observaron valores 0 (inválidos). |
| `MMSI_String` | Entero | Identificador | Mismo MMSI que el campo anterior. | A pesar del nombre, en la captura llega como número. |
| `ShipName` | Texto | Texto no estructurado | Nombre del barco, máximo 20 caracteres. | Rellenado con espacios al final; vacío en 0.7 % de las posiciones. |
| `latitude` | Decimal | Cuantitativa | Latitud en grados decimales (WGS-84). | Rango observado: -76.9 a 71.6. |
| `longitude` | Decimal | Cuantitativa | Longitud en grados decimales (WGS-84). | Rango observado: -175.2 a 177.4. |
| `time_utc` | Texto (fecha-hora) | Temporal | Momento UTC en que AISStream recibió el mensaje, con precisión de nanosegundos. | Formato `2026-10-12 05:14:13.502595905 +0000 UTC` (no es ISO-8601). |

**`PositionReport`** (Mensajes AIS 1, 2 y 3; 48,366 mensajes en la captura)

| Atributo | Tipo | Clase | Significado | Valores especiales / observaciones |
|---|---|---|---|---|
| `MessageID` | Entero | Cualitativa | Número del mensaje AIS: 1 (programado), 2 (asignado) o 3 (en respuesta a una interrogación). | Observado: 1 (64 %), 3 (35 %), 2 (1 %). |
| `RepeatIndicator` | Entero 0-3 | Cuantitativa (discreta) | Veces que el mensaje fue retransmitido por repetidores. | 3 = no repetir más. |
| `UserID` | Entero | Identificador | MMSI del barco que emite el reporte. | Igual a `MetaData.MMSI`. |
| `Valid` | Booleano | Cualitativa | Indica si el mensaje decodificó correctamente. | Siempre `true` en la captura. |
| `NavigationalStatus` | Entero 0-15 | Cualitativa | Estado de navegación declarado por la tripulación. | 0 = bajo motor, 1 = fondeado, 2 = sin gobierno, 3 = maniobra restringida, 4 = limitado por calado, 5 = amarrado, 6 = varado, 7 = pescando, 8 = navegando a vela, 11 = remolcando a popa, 12 = empujando o remolcando al costado, 14 = baliza AIS-SART activa, 15 = no definido (7.4 % de las posiciones). |
| `RateOfTurn` | Entero | Cuantitativa | Velocidad de giro codificada (0 = sin giro; el signo indica la dirección). | -128 = no disponible (41 % de las posiciones); ±127 = girando a más de 5° cada 30 s. |
| `Sog` | Decimal | Cuantitativa | Speed Over Ground: velocidad sobre el fondo, en nudos, con resolución de 0.1. | 102.3 = no disponible (0.3 %). |
| `PositionAccuracy` | Booleano | Cualitativa | Precisión de la posición: `true` = alta (menos de 10 m), `false` = baja. | `true` en el 60 % de los reportes. |
| `Longitude` | Decimal | Cuantitativa | Longitud en grados decimales. | 181 = no disponible. |
| `Latitude` | Decimal | Cuantitativa | Latitud en grados decimales. | 91 = no disponible. |
| `Cog` | Decimal | Cuantitativa | Course Over Ground: rumbo sobre el fondo, en grados (0 a 359.9). | 360 = no disponible (20 %). |
| `TrueHeading` | Entero | Cuantitativa | Dirección real de la proa, en grados (0 a 359). | 511 = no disponible (43 %). |
| `Timestamp` | Entero 0-63 | Temporal | Segundo UTC del minuto en que el barco generó la posición (no es una fecha completa). | 60 = no disponible (4.3 %); 61 = ingreso manual; 62 = estimada (dead reckoning); 63 = sistema de posicionamiento inoperativo. |
| `SpecialManoeuvreIndicator` | Entero | Cualitativa | Indica si el barco realiza una maniobra especial. | 0 = no disponible, 1 = no realiza maniobra, 2 = realiza maniobra; 3 = reservado (se observó 48 veces). |
| `Spare` | Entero | Sin significado | Bits de relleno del protocolo. | Se ignora. |
| `Raim` | Booleano | Cualitativa | Receiver Autonomous Integrity Monitoring: `true` si el receptor GPS verifica la integridad de su posición. | |
| `CommunicationState` | Entero | Cuantitativa (técnica) | Estado de sincronización y de franjas de tiempo de la radio (SOTDMA/ITDMA). | Útil solo para análisis de la red de radio. |

**`ShipStaticData`** (Mensaje AIS 5; 8,746 mensajes en la captura)

| Atributo | Tipo | Clase | Significado | Valores especiales / observaciones |
|---|---|---|---|---|
| `MessageID` | Entero | Cualitativa | Número del mensaje AIS. | Siempre 5. |
| `RepeatIndicator` | Entero 0-3 | Cuantitativa (discreta) | Veces que el mensaje fue retransmitido por repetidores. | |
| `UserID` | Entero | Identificador | MMSI del barco. | Igual a `MetaData.MMSI`. |
| `Valid` | Booleano | Cualitativa | Indica si el mensaje decodificó correctamente. | Siempre `true` en la captura. |
| `AisVersion` | Entero 0-3 | Cualitativa | Versión del estándar ITU-R M.1371 que cumple el equipo AIS del barco. | Observado: 0, 1 y 2. |
| `ImoNumber` | Entero | Identificador | Número IMO del barco (7 dígitos), único y permanente del casco. | 0 = no disponible (47.6 %). |
| `CallSign` | Texto | Texto no estructurado | Indicativo de llamada de radio (hasta 7 caracteres). | Vacío en 2.1 %. |
| `Name` | Texto | Texto no estructurado | Nombre del barco (hasta 20 caracteres). | Vacío en 0.1 %. |
| `Type` | Entero 0-99 | Cualitativa | Código de tipo de barco y carga. | 0 = no disponible; 30 = pesca; 31-32 = remolque; 35 = militar; 36 = vela; 37 = recreo; 50 = piloto; 51 = búsqueda y rescate; 52 = remolcador; 60-69 = pasajeros; 70-79 = carga; 80-89 = tanque; 90-99 = otros. Más frecuentes: 70, 52, 79, 37, 80. |
| `Dimension` | Objeto `A`, `B`, `C`, `D` | Cuantitativa | Dimensiones en metros, medidas desde la antena GPS: `A` hacia la proa, `B` hacia la popa, `C` hacia babor, `D` hacia estribor. Eslora = A + B; manga = C + D. | 0 = no disponible (las cuatro en cero: 2.4 %). Máximos observados: A 511, B 333, C 63, D 63. |
| `MaximumStaticDraught` | Decimal | Cuantitativa | Calado máximo del barco en metros, con resolución de 0.1. | 0 = no disponible (18 %); máximo observado 25.5. |
| `Destination` | Texto | Texto no estructurado | Destino declarado por la tripulación (hasta 20 caracteres). | Vacío en 14 %; abreviaturas y errores frecuentes. |
| `Eta` | Objeto `Month`, `Day`, `Hour`, `Minute` | Temporal | Llegada estimada al destino, declarada por la tripulación. No incluye año. | No disponible: mes 0, día 0, hora 24, minuto 60; también se observa `0/0/0/0`. Juntos suman 26 % de los registros. |
| `FixType` | Entero 0-15 | Cualitativa | Tipo de dispositivo de posicionamiento: 1 = GPS, 2 = GLONASS, 3 = GPS/GLONASS combinado, 6 = sistema de navegación integrado, 7 = topografía (surveyed), 8 = Galileo. | 0 y 15 = no definido (alrededor del 38 %). |
| `Dte` | Booleano | Cualitativa | Bit DTE (Data Terminal Equipment) del estándar: `false` = terminal de datos disponible, `true` = no disponible. | `true` en 2.7 %. |
| `Spare` | Booleano | Sin significado | Bit de relleno del protocolo. | Se ignora. |

### Catálogo de Tipos de Mensajes de AIS Stream
Se enlistan los tipos de mensajes y una descripción, se tomó en cuenta la división que presenta el stream para hacer la lista. Los 4 modelos de *Envelope* describen el protocolo y no cuentan entre los 25 tipos de mensaje filtrables.

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
* **`LongRangeAisBroadcastMessage`**: Datos de posición y estado optimizados para ser capturados por satélites u otros sistemas de largo alcance (Mensaje AIS 27).

#### Static and Voyage (Datos del Buque y Travesía)
Información administrativa, física y logística sobre la embarcación y su ruta comercial.

* **`ShipStaticData`**: Datos estáticos y de travesía del buque (Mensaje AIS 5). Contiene el nombre del barco (`Name`), número IMO, tipo de nave (`Type`), dimensiones físicas (`Dimension`), puerto de destino (`Destination`) y tiempo estimado de llegada (`Eta`).
* **`StaticDataReport`**: Reporte en dos partes que transmite los metadatos estáticos de embarcaciones con transceptores Clase B (Mensaje AIS 24).

#### Binary Data (Cargas Útiles de Datos Binarios)
Mensajes orientados a la transmisión de datos personalizados o estructurados entre estaciones.

* **`AddressedBinaryMessage`**: Transmisión de datos binarios dirigida a una embarcación o estación específica por su MMSI (Mensaje AIS 6).
* **`BinaryAcknowledge`**: Acuse de recibo de la recepción exitosa de un mensaje binario previo direccionado (Mensaje AIS 7).
* **`BinaryBroadcastMessage`**: Emisión generalizada de datos binarios difundida a todas las estaciones en rango (Mensaje AIS 8).
* **`SingleSlotBinaryMessage`**: Mensaje binario compacto de longitud reducida enviado en un solo segmento de tiempo (Mensaje AIS 25).
* **`MultiSlotBinaryMessage`**: Mensaje binario extenso enviado a través de múltiples segmentos de tiempo consecutivos (Mensaje AIS 26).
* **`GnssBroadcastBinaryMessage`**: Difusión de correcciones diferenciales GNSS desde una estación base para mejorar la precisión de las posiciones (Mensaje AIS 17).

#### Network and Control (Gestión de Red y Canales)
Comandos del sistema para la gestión del espectro radioeléctrico y asignación de frecuencias.

* **`Interrogation`**: Solicitud enviada por una estación base o barco para requerir datos específicos a otra nave (Mensaje AIS 15).
* **`ChannelManagement`**: Instrucciones para cambiar de canal de transmisión de radiofrecuencia VHF dentro de una zona geográfica definida (Mensaje AIS 22).
* **`DataLinkManagementMessage`**: Datos técnicos de asignación e intercalado de franjas horarias de radio (Slots TDMA / Mensaje AIS 20) para el mantenimiento del enlace de datos marítimo.
* **`GroupAssignmentCommand`**: Instrucciones enviadas a un grupo de barcos para definir sus intervalos de transmisión o frecuencias (Mensaje AIS 23).
* **`DataLinkManagementMessageData`**: Sub-estructura de datos del `DataLinkManagementMessage` (bloques de franjas reservadas).
* **`AssignedModeCommand`**: Comando de una estación base que asigna a una nave su franja de transmisión (Mensaje AIS 16).
* **`CoordinatedUTCInquiry`**: Consulta de fecha y hora UTC dirigida a otra estación (Mensaje AIS 10).
* **`UnknownMessage`**: Mensaje AIS que el stream no pudo clasificar en ninguno de los demás tipos.

#### Safety (Seguridad y Alertas)
Alertas críticas, acuses de recibo y comunicaciones de emergencia marítima.

* **`AddressedSafetyMessage`**: Notificación de seguridad dirigida específicamente a un receptor en particular (Mensaje AIS 12).
* **`SafetyBroadcastMessage`**: Alerta o aviso de seguridad marítima emitido en abierto a todos los barcos en la zona (Mensaje AIS 14).
* **`AidsToNavigationReport`**: Información enviada por balizas, faros o boyas de señalización (AtoN / Mensaje AIS 21), indicando su ubicación y estado.


### Clasificación de Variables
Se presentan algunas de las variables que podemos encontrar dentro de los *Message* y *MetaData*. La clasificación completa de los atributos de `PositionReport`, `ShipStaticData` y `MetaData` está en la columna *Clase* de las tablas del diccionario.

* **Variables Cuantitativas:**
  * `latitude`, `longitude` (Coordenadas geográficas).
  * `Sog` (Velocidad en nudos).
  * `Cog`, `TrueHeading` (Ángulos de dirección/rumbo).
  * `Dimension.A`, `Dimension.B`, `Dimension.C`, `Dimension.D` (Dimensiones físicas de la nave en metros).
  * `MaximumStaticDraught` (Calado máximo del barco, en *ShipStaticData*).

* **Variables Cualitativas:**
  * `MessageType` (Tipo de evento).
  * `NavigationalStatus` (Estado de navegación).
  * `Type` (Categoría de buque, código numérico en *ShipStaticData*).

* **Texto No Estructurado:**
  * `ShipName` (en *MetaData*) / `Name` (en *ShipStaticData*): nombre comercial o registrado.
  * `Destination` (Destino en texto abierto ingresado por la tripulación; suele contener tipografía errónea o abreviaturas no estandarizadas).
  * `CallSign` (Indicativo de llamada de radio).

* **Series Temporales:**
  * `time_utc` (en *MetaData*: marca de tiempo UTC de recepción del mensaje en el stream).
  * `Timestamp` (en *PositionReport*: solo el segundo UTC del minuto, 0-59, en que el barco generó la posición; **no** es una fecha completa).
  * `Eta` (en *ShipStaticData*: llegada estimada declarada por la tripulación, como mes/día/hora/minuto, sin año).

### Consideraciones Éticas y Privacidad

* **Sensibilidad de la Información:** Aunque los datos AIS son de difusión pública por seguridad marítima mundial (IMO/OMI), el monitoreo continuo de embarcaciones pesqueras o recreativas en tiempo real puede exponer patrones de trabajo o ubicaciones sensibles. También podrían presentan riesgos de seguridad si no se gestionan adecuadamente los controles de acceso a los paneles analíticos

* **Calidad y Sesgo:** El campo `Destination` y otros campos son ingresados manualmente por operadores humanos, lo que introduce errores de tipeo y campos nulos.

* **Cobertura desigual:** el stream depende de la red de receptores; hay zonas con mucha cobertura (costas, puertos) y otras casi sin ella (océano abierto), por lo que la ausencia de datos no implica ausencia de barcos.

* **Datos no confiables por diseño:** el transmisor AIS puede apagarse o configurarse con datos falsos (identidad, posición). Los valores "no disponible" del protocolo (p. ej. `TrueHeading = 511`) deben tratarse como nulos y no como datos reales.

* **Garantías del servicio:** AISStream no ofrece SLA ni reenvío de eventos perdidos; si el consumidor es lento, el servicio descarta mensajes. Esto limita las conclusiones sobre completitud.

## 3. Integrantes

* Lucas Garcia Arredondo
* Tania Dominguez
* Alvaro Zunzunegui

## 4. Cómo correrlo (Etapa 1)

```bash
git clone https://github.com/Equipo8-BDNR/Maritime-events-WebSocket.git
cd Maritime-events-WebSocket
uv sync
cp .env.example .env
```

Después se edita `.env` y se pone la API key propia (`AISSTREAM_API_KEY`). Cada integrante genera la suya en [https://aisstream.io/account](https://aisstream.io/account). El archivo `.env` está en `.gitignore` y la llave nunca se sube al repositorio. AISStream no permite conexiones directas desde el navegador: el consumidor corre del lado servidor.

Notas del servicio (según su documentación):

* La suscripción exige `BoundingBoxes`; `FiltersShipMMSI` y `FilterMessageTypes` son opcionales.
* La suscripción debe enviarse dentro de los 3 segundos posteriores a abrir la conexión.
* Máximo 3 conexiones por cuenta y 3 por IP.
* Se debe habilitar `permessage-deflate`; desde septiembre de 2026 las conexiones sin compresión tienen límite de ancho de banda.

## 5. Muestra capturada (referencia)

Captura de 10 minutos con cobertura global (`BoundingBoxes` de todo el mundo) y solo `PositionReport` y `ShipStaticData`, hecha con `scripts/capture.py` (12-oct-2026). El archivo crudo se guarda en `data/` y no se sube al repositorio.

| Métrica | Valor |
|---|---|
| Mensajes recibidos | 57,113 en 611 s (≈ 93 mensajes/s, estable) |
| `PositionReport` / `ShipStaticData` | 48,366 / 8,746 (≈ 5.5 a 1) |
| Embarcaciones distintas (MMSI) | 18,207 |
| Tamaño del JSON crudo | ≈ 32 MB (≈ 190 MB/hora, ≈ 4.6 GB/día) |

Observaciones de calidad de datos en la muestra:

* `TrueHeading = 511` (no disponible) en el 42.6 % de los `PositionReport`; `Cog = 360` (no disponible) en el 19.9 %.
* `Timestamp ≥ 60` (no disponible) en el 4.3 % de los `PositionReport`.
* `Destination` vacío en el 14.0 % de los `ShipStaticData`.
* `Eta` sin valor real en el 26 % de los `ShipStaticData` (`0/0/24/60`: 16 %, `0/0/0/0`: 10 %); además no incluye año.
* `RateOfTurn = -128` (no disponible) en el 41 % de los `PositionReport`.
* `ImoNumber = 0` en el 47.6 % y `MaximumStaticDraught = 0` en el 18.2 % de los `ShipStaticData`; `UserID`/`MMSI` = 0 aparece en algunos mensajes.
* `ShipName` en *MetaData* viene rellenado con espacios al final (20 caracteres); hay que aplicar `strip`.
* `time_utc` no es ISO-8601 (ejemplo: `2026-10-12 05:14:13.502595905 +0000 UTC`) y tiene precisión de nanosegundos.
* El primer mensaje del stream es un `SubscriptionConfirmation`, no un evento marítimo.
