#!/usr/bin/env python
"""
Error Busters - Demo Script

Este script demuestra las capacidades principales del sistema Error Busters.
"""

import requests
import json
import time
import os
import csv
import sys

API_BASE = "http://localhost:5000"

def print_header(text):
    """Imprime un encabezado en la consola."""
    print("\n" + "=" * 80)
    print(f" {text} ".center(80, "="))
    print("=" * 80 + "\n")

def print_json(data):
    """Imprime datos JSON de forma legible."""
    print(json.dumps(data, indent=2, ensure_ascii=False))

def create_sample_file(name, columns, rows, encoding='utf-8'):
    """Crea un archivo CSV de muestra."""
    filename = f"{name}.csv"
    with open(filename, 'w', newline='', encoding=encoding) as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for i in range(rows):
            writer.writerow([f"value{i}" for _ in columns])
    print(f"Creado archivo de muestra: {filename}")
    return filename

def demo_file_validation():
    """Demostración de validación de archivos."""
    print_header("DEMOSTRACIÓN DE VALIDACIÓN DE ARCHIVOS")
    
    # Caso 1: Archivo válido
    print("Caso 1: Archivo con esquema correcto")
    filename = create_sample_file(
        "valid_sales", 
        ['id', 'date', 'product', 'amount', 'customer'],
        5
    )
    
    with open(filename, 'rb') as f:
        files = {'file': f}
        data = {'file_type': 'sales_data', 'job_name': 'nightly_import'}
        response = requests.post(f"{API_BASE}/api/validate", files=files, data=data)
    
    print_json(response.json())
    
    # Caso 2: Archivo con columnas incorrectas
    print("\nCaso 2: Archivo con columnas incorrectas")
    filename = create_sample_file(
        "invalid_sales", 
        ['user_id', 'transaction_date', 'item', 'price', 'buyer'],
        5
    )
    
    with open(filename, 'rb') as f:
        files = {'file': f}
        data = {'file_type': 'sales_data', 'job_name': 'nightly_import'}
        response = requests.post(f"{API_BASE}/api/validate", files=files, data=data)
    
    print_json(response.json())

def demo_log_analysis():
    """Demostración de análisis de logs."""
    print_header("DEMOSTRACIÓN DE ANÁLISIS DE LOGS")
    
    sample_logs = [
        {
            "title": "Error de Conexión a Base de Datos",
            "log": """
[2023-05-03 14:25:12] ERROR: Could not connect to database at 10.0.1.5:3306. Connection timed out.
[2023-05-03 14:25:13] ERROR: Database connection failed after 3 retries
[2023-05-03 14:25:14] CRITICAL: Job failed: nightly_import - Unable to establish database connection
            """,
            "job": "nightly_import"
        },
        {
            "title": "Error de Codificación de Archivo",
            "log": """
[2023-05-03 09:15:33] WARNING: File encoding issue detected
[2023-05-03 09:15:33] ERROR: Cannot decode byte 0xf1 in position 244: invalid start byte
[2023-05-03 09:15:33] ERROR: Failed to process customers.csv - encoding error
            """,
            "job": "customer_import"
        },
        {
            "title": "Error de Permisos",
            "log": """
[2023-05-03 11:30:45] ERROR: Permission denied: /var/data/reports/monthly/
[2023-05-03 11:30:45] ERROR: Cannot write output file. Check directory permissions.
[2023-05-03 11:30:46] CRITICAL: Monthly report generation failed
            """,
            "job": "monthly_report"
        }
    ]
    
    for log_entry in sample_logs:
        print(f"\nAnalizando: {log_entry['title']}")
        data = {
            "log": log_entry["log"],
            "job": log_entry["job"]
        }
        response = requests.post(f"{API_BASE}/api/analyze-log", json=data)
        print_json(response.json())

def demo_job_rerun():
    """Demostración de re-ejecución de jobs."""
    print_header("DEMOSTRACIÓN DE RE-EJECUCIÓN DE JOBS")
    
    jobs = ["nightly_import", "customer_import", "monthly_report"]
    
    for job in jobs:
        print(f"\nRe-ejecutando job: {job}")
        data = {"job": job}
        response = requests.post(f"{API_BASE}/api/rerun", json=data)
        print_json(response.json())

def demo_zendesk_hook():
    """Demostración de integración con Zendesk."""
    print_header("DEMOSTRACIÓN DE WEBHOOK ZENDESK")
    
    sample_ticket = {
        "ticket": {
            "id": 12345,
            "subject": "Error en proceso nightly_import",
            "description": """
Buenas tardes equipo de soporte,

El proceso de importación nocturna falló anoche y no tenemos los datos actualizados.

Job: nightly_import
Log: https://storage.example.com/logs/nightly_import_20230503.log

¿Podrían revisar y resolver el problema lo antes posible?

Gracias,
Cliente
            """
        }
    }
    
    print("Enviando ticket de ejemplo a través del webhook:")
    response = requests.post(f"{API_BASE}/api/zendesk-hook", json=sample_ticket)
    print_json(response.json())

def demo_stats():
    """Demostración de estadísticas del sistema."""
    print_header("ESTADÍSTICAS DEL SISTEMA")
    
    # Estadísticas generales
    print("Estadísticas Generales:")
    response = requests.get(f"{API_BASE}/api/stats")
    print_json(response.json())
    
    # Estadísticas del MCP
    print("\nEstadísticas del Servidor MCP:")
    response = requests.get(f"{API_BASE}/api/mcp-stats")
    print_json(response.json())

def demo_contextual_messaging():
    """Demostración de personalización contextual de mensajes según audiencia."""
    print_header("DEMOSTRACIÓN DE PERSONALIZACIÓN CONTEXTUAL")
    
    # Mensaje y error de ejemplo
    sample_message = "Error de conexión a la base de datos. No se pudo establecer la conexión con el servidor MySQL."
    sample_error = {
        "type": "connection_error",
        "message": "Error de conexión a la base de datos. No se pudo establecer la conexión con el servidor MySQL.",
        "log": "Error: Could not connect to database at 10.0.1.5:3306. Connection timed out after 30 seconds."
    }
    
    job_name = "nightly_import"
    
    # Demostrar personalización para diferentes audiencias
    audience_types = ["engineer", "support", "business", "client"]
    
    print("Personalización de mensaje simple:\n")
    for audience in audience_types:
        print(f"\n--- Mensaje para {audience.upper()} ---")
        data = {
            "message": sample_message,
            "job": job_name,
            "audience_type": audience
        }
        response = requests.post(f"{API_BASE}/api/contextualized-message", json=data)
        result = response.json()
        print(result['contextualized_message'])
    
    print("\n\nPersonalización de respuesta completa con error:\n")
    for audience in audience_types:
        print(f"\n--- Respuesta completa para {audience.upper()} ---")
        data = {
            "message": sample_message,
            "job": job_name,
            "audience_type": audience,
            "error_data": sample_error
        }
        response = requests.post(f"{API_BASE}/api/contextualized-message", json=data)
        result = response.json()
        full_response = result['full_response']
        
        print(f"Título: {full_response['title']}")
        print(f"Mensaje: {full_response['message']}")
        print("Pasos a seguir:")
        for step in full_response['next_steps']:
            print(f"- {step}")

def main():
    """Ejecuta todas las demostraciones."""
    print_header("ERROR BUSTERS - DEMOSTRACIÓN DEL SISTEMA")
    
    print("Verificando que el servidor esté en funcionamiento...")
    try:
        response = requests.get(API_BASE)
        if response.status_code != 200:
            print(f"Error: El servidor devolvió código {response.status_code}")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"Error: No se pudo conectar al servidor en {API_BASE}")
        print("Asegúrate de que el servidor esté en ejecución con 'python deeptrace.py'")
        sys.exit(1)
    
    print("Servidor en funcionamiento!")
    
    # Ejecutar demostraciones
    demo_file_validation()
    time.sleep(1)
    
    demo_log_analysis()
    time.sleep(1)
    
    demo_job_rerun()
    time.sleep(1)
    
    demo_zendesk_hook()
    time.sleep(1)
    
    demo_stats()
    time.sleep(1)
    
    demo_contextual_messaging()
    
    print_header("DEMOSTRACIÓN COMPLETA")
    print("""
El sistema Error Busters está ahora en funcionamiento y ha demostrado sus capacidades
principales:

1. Validación automática de archivos con detección de errores
2. Análisis de logs utilizando IA para identificar patrones
3. Re-ejecución automática de jobs fallidos
4. Integración con sistemas de tickets (Zendesk)
5. Monitoreo continuo a través del Servidor MCP
6. Personalización contextual de mensajes según:
   - Entorno (desarrollo, pruebas, producción)
   - Audiencia (técnico, soporte, negocio, cliente)
   - Historial de errores y su frecuencia
   - Criticidad del job y su impacto en el negocio

El sistema continuará aprendiendo de cada nuevo error, mejorando sus diagnósticos
y recomendaciones con el tiempo.
    """)

if __name__ == "__main__":
    main() 