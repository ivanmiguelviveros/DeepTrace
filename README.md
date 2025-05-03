# Error Busters: AI-Powered Error Analysis & Resolution System

Error Busters es una solución basada en inteligencia artificial para detectar, diagnosticar y resolver errores en los procesos del sistema en tiempo real. Nuestra plataforma combina técnicas avanzadas de NLP, clustering y aprendizaje automático para minimizar el tiempo de resolución de incidentes, reducir la intervención manual y mejorar la comunicación tanto con ingenieros como con usuarios finales.

## Características Principales

- **Detección Automática de Errores**: Identifica automáticamente problemas en archivos (codificación, esquemas) y logs de procesos.
  
- **Sistema MCP (Monitor, Classify, Predict)**: Servidor inteligente que monitorea continuamente errores, agrupa incidentes similares y predice soluciones basadas en casos anteriores.
  
- **Análisis Predictivo de Patrones**: Utiliza clustering (DBSCAN) y vectorización TF-IDF para identificar patrones recurrentes en logs de error.
  
- **Automatización de Re-ejecución**: Basado en el análisis del error, determina y dispara automáticamente flujos de re-ejecución.
  
- **Diagnóstico con NLP**: Analiza los logs de error utilizando procesamiento de lenguaje natural para extraer información clave y proponer soluciones.
  
- **Sistema de Documentación Dinámica**: Aprende continuamente de cada caso resuelto, enriqueciendo la base de conocimientos para futuras referencias.
  
- **Integración con Zendesk**: Automatiza la gestión de tickets, proporcionando diagnósticos técnicos para ingenieros y mensajes claros para clientes.

## Arquitectura

El sistema consta de los siguientes componentes:

1. **API REST (Flask)**: Expone endpoints para validación de archivos, análisis de logs, re-ejecución de jobs y webhooks para sistemas de tickets.

2. **Servidor MCP**: Componente central de IA que:
   - Monitorea continuamente errores en el sistema
   - Agrupa errores similares mediante clustering
   - Identifica patrones conocidos usando coincidencia de palabras clave
   - Dispara alertas cuando se detectan múltiples errores similares
   - Ejecuta automáticamente procedimientos de recuperación

3. **Motor de Análisis**: Utiliza técnicas de NLP y similitud de coseno para encontrar errores similares en la base de conocimiento y proporcionar diagnósticos precisos.

4. **Base de Conocimiento**: Almacena patrones de error, soluciones y recomendaciones que se enriquecen con cada nuevo caso.

## Flujo de Proceso

1. Un error es detectado (validación de archivo, fallo de job, ticket de soporte)
2. El sistema analiza el error usando el Servidor MCP y el motor de análisis
3. Se identifica el patrón y se recupera la solución más probable
4. El sistema proporciona dos tipos de mensajes:
   - **Mensaje técnico**: Diagnóstico detallado para ingenieros
   - **Mensaje para cliente**: Explicación clara y no técnica
5. Se disparan automáticamente procesos de re-ejecución cuando es posible
6. El caso se almacena para enriquecer la base de conocimiento

## Instalación y Uso

### Requisitos

```
python 3.8+
```

Instala las dependencias:

```bash
pip install -r requirements.txt
```

### Ejecución

```bash
python deeptrace.py
```

El servidor estará disponible en `http://localhost:5000`

## Endpoints API

- `GET /`: Información general de la API
- `POST /api/validate`: Valida un archivo (formato, encoding, columnas)
- `POST /api/rerun`: Re-ejecuta un job específico
- `POST /api/analyze-log`: Analiza un log para detectar patrones de error
- `POST /api/zendesk-hook`: Webhook para procesar tickets de Zendesk
- `GET /api/stats`: Estadísticas de errores detectados
- `GET /api/mcp-stats`: Estadísticas del Servidor MCP

## Configuración

Crea un archivo `.env` con las siguientes variables:

```
ZENDESK_SUBDOMAIN=your_subdomain
ZENDESK_API_TOKEN=your_token
ZENDESK_USER=your_email/token
MCP_CHECK_INTERVAL=60
MCP_ERROR_THRESHOLD=3
MCP_SIMILARITY_THRESHOLD=0.7
``` 