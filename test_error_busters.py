#!/usr/bin/env python
"""
Error Busters - Tests Unitarios

Este archivo contiene tests unitarios para las funcionalidades
principales del sistema Error Busters.
"""

import unittest
import json
import datetime
import os
import tempfile
from unittest.mock import patch, MagicMock

# Importar módulos del sistema
from context_analyzer import ContextAnalyzer, AudienceType, Environment
from mcp_server import MCPServer

class TestContextAnalyzer(unittest.TestCase):
    """Tests para el analizador de contexto."""
    
    def setUp(self):
        """Prepara el entorno para las pruebas."""
        # Crear un archivo de contexto temporal para las pruebas
        self.temp_context_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_context_file.close()
        
        # Escribir datos de contexto de prueba
        test_context = {
            "systems": {
                "test_system": {
                    "name": "Sistema de Prueba",
                    "environment": "production",
                    "criticality": "high",
                    "technical_contact": "tech@test.com",
                    "business_contact": "business@test.com"
                }
            },
            "jobs": {
                "test_job": {
                    "system": "test_system",
                    "criticality": "high",
                    "schedule": "daily",
                    "dependencies": ["database", "file_storage"],
                    "business_impact": "Impacto de prueba en el negocio"
                }
            }
        }
        
        with open(self.temp_context_file.name, 'w') as f:
            json.dump(test_context, f)
            
        # Inicializar el analizador de contexto
        self.analyzer = ContextAnalyzer()
        self.analyzer.load_system_context(self.temp_context_file.name)
        
        # Añadir algunos errores de prueba
        self.test_error = {
            "type": "connection_error",
            "message": "No se pudo conectar a la base de datos",
            "log": "Error: Could not connect to database at 10.0.1.5:3306. Connection timed out."
        }
        self.analyzer.add_error_to_history("test_job", self.test_error)
    
    def tearDown(self):
        """Limpia después de las pruebas."""
        # Eliminar archivo temporal
        if os.path.exists(self.temp_context_file.name):
            os.unlink(self.temp_context_file.name)
    
    def test_load_system_context(self):
        """Prueba la carga del contexto del sistema."""
        # Verificar que el contexto se cargó correctamente
        self.assertIn("test_system", self.analyzer.system_context)
        self.assertIn("test_job", self.analyzer.job_metadata)
        self.assertEqual("production", self.analyzer.system_context["test_system"]["environment"])
        self.assertEqual("high", self.analyzer.job_metadata["test_job"]["criticality"])
    
    def test_add_error_to_history(self):
        """Prueba la adición de errores al historial."""
        # Añadir un nuevo error
        new_error = {
            "type": "file_error",
            "message": "No se encontró el archivo",
            "log": "Error: File not found: /path/to/file.csv"
        }
        self.analyzer.add_error_to_history("test_job", new_error)
        
        # Verificar que se añadió correctamente
        self.assertEqual(2, len(self.analyzer.error_history["test_job"]))
        self.assertEqual("file_error", self.analyzer.error_history["test_job"][1]["type"])
    
    def test_get_job_context(self):
        """Prueba la obtención del contexto de un job."""
        context = self.analyzer.get_job_context("test_job")
        
        # Verificar el contexto obtenido
        self.assertEqual("test_job", context["job_name"])
        self.assertEqual("test_system", context["system"])
        self.assertEqual("high", context["criticality"])
        self.assertEqual("Impacto de prueba en el negocio", context["business_impact"])
    
    def test_contextualize_message_for_engineer(self):
        """Prueba la contextualización de mensajes para ingenieros."""
        message = "Error de conexión a la base de datos."
        result = self.analyzer.contextualize_message(
            message,
            "test_job",
            AudienceType.ENGINEER
        )
        
        # Verificar adaptaciones para ingenieros
        self.assertIn("[URGENTE]", result)  # Por ser un job crítico en producción
        self.assertIn("Error similar ocurrió", result)  # Historial
    
    def test_contextualize_message_for_client(self):
        """Prueba la contextualización de mensajes para clientes."""
        message = "Error de conexión a la base de datos en el servidor 10.0.1.5."
        result = self.analyzer.contextualize_message(
            message,
            "test_job",
            AudienceType.CLIENT
        )
        
        # Verificar adaptaciones para clientes
        self.assertIn("Estamos trabajando en resolver un problema", result)
        self.assertNotIn("servidor 10.0.1.5", result)  # Técnico eliminado
        self.assertIn("componente del sistema", result)  # Reemplazado por texto genérico
    
    def test_generate_context_aware_response(self):
        """Prueba la generación de respuestas adaptadas al contexto."""
        response = self.analyzer.generate_context_aware_response(
            "test_job",
            self.test_error,
            AudienceType.SUPPORT
        )
        
        # Verificar respuesta
        self.assertIn("title", response)
        self.assertIn("message", response)
        self.assertIn("next_steps", response)
        self.assertIn("sistema test_system", response["message"])
    
    def test_analyze_dependencies(self):
        """Prueba el análisis de dependencias."""
        # Añadir un error que menciona la base de datos
        db_error = {
            "type": "db_error",
            "message": "Error de base de datos",
            "log": "Error: Database connection refused"
        }
        self.analyzer.add_error_to_history("test_job", db_error)
        
        # Analizar dependencias
        deps = self.analyzer.analyze_dependencies("test_job")
        
        # Verificar análisis de dependencias
        self.assertEqual(2, len(deps))  # database y file_storage
        db_dep = next((d for d in deps if d["name"] == "database"), None)
        self.assertIsNotNone(db_dep)
        self.assertTrue(db_dep["possible_cause"])  # La BD aparece como posible causa


class TestMCPServer(unittest.TestCase):
    """Tests para el servidor MCP."""
    
    def setUp(self):
        """Prepara el entorno para las pruebas."""
        # Inicializar servidor MCP
        self.mcp = MCPServer()
        
        # Error de prueba
        self.test_error = {
            "timestamp": datetime.datetime.now().isoformat(),
            "type": "connection_error",
            "job": "test_job",
            "log": "Error: Could not connect to database at 10.0.1.5:3306. Connection timed out."
        }
    
    def test_add_error(self):
        """Prueba la adición de errores al MCP."""
        # Añadir error
        self.mcp.add_error(self.test_error)
        
        # Verificar que se añadió correctamente
        self.assertEqual(1, len(self.mcp.error_db))
        self.assertEqual("connection_error", self.mcp.error_db[0]["type"])
    
    @patch('requests.post')
    def test_trigger_rerun(self, mock_post):
        """Prueba la re-ejecución de jobs."""
        # Configurar mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Ejecutar
        result = self.mcp._trigger_rerun("test_job")
        
        # Verificar
        self.assertTrue(result)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual('http://localhost:5000/api/rerun', args[0])
        self.assertEqual({'job': 'test_job'}, kwargs['json'])
    
    def test_analyze_log(self):
        """Prueba el análisis de logs."""
        # Añadir error al historial
        self.mcp.add_error(self.test_error)
        
        # Analizar un log similar
        log = "Error: Database connection timed out at 10.0.1.5:3306"
        result = self.mcp.analyze_log(log, "test_job")
        
        # Verificar análisis
        self.assertEqual("success", result["status"])
        self.assertIn("pattern_detected", result)
        self.assertEqual("database_connection", result["pattern_detected"])
    
    def test_find_matching_pattern(self):
        """Prueba la identificación de patrones de error."""
        # Log con error de base de datos
        log = "Error: Database connection timed out at 10.0.1.5:3306"
        pattern = self.mcp._find_matching_pattern(log)
        
        # Verificar patrón identificado
        self.assertIsNotNone(pattern)
        self.assertEqual("database_connection", pattern["pattern_name"])
        
        # Probar con otro tipo de error
        log = "Error: Permission denied: cannot write to /var/log/app.log"
        pattern = self.mcp._find_matching_pattern(log)
        self.assertEqual("permission_denied", pattern["pattern_name"])


class TestEndToEndFlow(unittest.TestCase):
    """Tests de flujo completo de Error Busters."""
    
    @patch('requests.post')
    def test_analyze_and_rerun_flow(self, mock_post):
        """Prueba el flujo completo de análisis y re-ejecución."""
        # Configurar mocks para el flujo
        mock_responses = {
            '/api/analyze-log': {
                'status': 'success',
                'pattern_detected': 'database_connection',
                'confidence': 'high',
                'engineer_message': 'Error de conexión a la base de datos detectado.',
                'client_message': 'Estamos experimentando problemas de conexión.'
            },
            '/api/rerun': {
                'status': 'success',
                'message': 'Job test_job re-execution triggered',
                'log': 'Triggered re-execution of job: test_job\nStatus: RUNNING',
                'estimated_completion': '2023-05-03T15:30:00.000000'
            }
        }
        
        def mock_post_side_effect(url, **kwargs):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            
            # Determinar qué respuesta devolver según la URL
            for endpoint, response_data in mock_responses.items():
                if endpoint in url:
                    mock_resp.json.return_value = response_data
                    return mock_resp
            
            # Valor por defecto
            mock_resp.json.return_value = {'status': 'error'}
            return mock_resp
        
        mock_post.side_effect = mock_post_side_effect
        
        # Simular flujo: Analizar log y rerun si es un error conocido
        log_data = {
            'log': 'Error: Database connection failed',
            'job': 'test_job'
        }
        
        # 1. Analizar log
        analyze_resp = requests.post('http://localhost:5000/api/analyze-log', json=log_data)
        analyze_result = analyze_resp.json()
        
        # Verificar análisis
        self.assertEqual('success', analyze_result['status'])
        self.assertEqual('database_connection', analyze_result['pattern_detected'])
        
        # 2. Si es un error conocido con alta confianza, hacer rerun
        if (analyze_result['status'] == 'success' and 
            analyze_result.get('confidence') == 'high'):
            
            rerun_data = {'job': log_data['job']}
            rerun_resp = requests.post('http://localhost:5000/api/rerun', json=rerun_data)
            rerun_result = rerun_resp.json()
            
            # Verificar rerun
            self.assertEqual('success', rerun_result['status'])
            self.assertIn('test_job', rerun_result['message'])
        
        # Verificar llamadas correctas
        self.assertEqual(2, mock_post.call_count)
        
        # Verificar primera llamada (analyze)
        args1, kwargs1 = mock_post.call_args_list[0]
        self.assertIn('/api/analyze-log', args1[0])
        self.assertEqual(log_data, kwargs1['json'])
        
        # Verificar segunda llamada (rerun)
        args2, kwargs2 = mock_post.call_args_list[1]
        self.assertIn('/api/rerun', args2[0])
        self.assertEqual(rerun_data, kwargs2['json'])


if __name__ == '__main__':
    unittest.main() 