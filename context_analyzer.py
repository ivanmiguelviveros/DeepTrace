#!/usr/bin/env python
"""
Error Busters - Módulo de Personalización Contextual

Este módulo permite adaptar los mensajes y análisis según diferentes contextos:
- Entorno (desarrollo, pruebas, producción)
- Audiencia (técnico, negocio, cliente)
- Historial del sistema y errores previos
"""

import json
import datetime
import re
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple

class Environment(Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"

class AudienceType(Enum):
    ENGINEER = "engineer"       # Personal técnico con conocimiento profundo
    SUPPORT = "support"         # Equipo de soporte con conocimiento intermedio
    BUSINESS = "business"       # Stakeholders de negocio con conocimiento limitado
    CLIENT = "client"           # Clientes externos con conocimiento mínimo

class JobCriticality(Enum):
    LOW = "low"                 # Jobs no críticos, pueden esperar
    MEDIUM = "medium"           # Jobs importantes pero no urgentes
    HIGH = "high"               # Jobs críticos que requieren atención inmediata
    CRITICAL = "critical"       # Jobs críticos con impacto en negocio

class ContextAnalyzer:
    def __init__(self):
        self.error_history = {}  # Historial de errores por job/sistema
        self.system_context = {}  # Información contextual de cada sistema
        self.job_metadata = {}   # Metadatos de los jobs (criticidad, dependencias, etc)
        
    def load_system_context(self, context_file: str = 'system_context.json'):
        """Carga el contexto del sistema desde un archivo JSON."""
        try:
            with open(context_file, 'r') as f:
                data = json.load(f)
                self.system_context = data.get('systems', {})
                self.job_metadata = data.get('jobs', {})
            return True
        except (FileNotFoundError, json.JSONDecodeError):
            # Si el archivo no existe o no es válido, creamos uno básico
            self._create_default_context(context_file)
            return False
    
    def _create_default_context(self, context_file: str):
        """Crea un archivo de contexto predeterminado si no existe."""
        default_context = {
            "systems": {
                "sales": {
                    "name": "Sistema de Ventas",
                    "environment": "production",
                    "criticality": "high",
                    "technical_contact": "tech_team@company.com",
                    "business_contact": "sales_manager@company.com"
                },
                "inventory": {
                    "name": "Sistema de Inventario",
                    "environment": "production",
                    "criticality": "medium",
                    "technical_contact": "tech_team@company.com",
                    "business_contact": "inventory_manager@company.com"
                }
            },
            "jobs": {
                "nightly_import": {
                    "system": "sales",
                    "criticality": "high",
                    "schedule": "daily",
                    "dependencies": ["database", "file_storage"],
                    "business_impact": "Actualización de datos de ventas para reportes diarios"
                },
                "customer_import": {
                    "system": "sales",
                    "criticality": "medium",
                    "schedule": "daily",
                    "dependencies": ["file_storage"],
                    "business_impact": "Actualización de datos de clientes"
                },
                "inventory_sync": {
                    "system": "inventory",
                    "criticality": "high",
                    "schedule": "hourly",
                    "dependencies": ["database", "erp_connection"],
                    "business_impact": "Sincronización de niveles de inventario con tiendas"
                }
            }
        }
        
        try:
            with open(context_file, 'w') as f:
                json.dump(default_context, f, indent=2)
        except Exception as e:
            print(f"Error creating default context file: {e}")
    
    def add_error_to_history(self, job_name: str, error_data: Dict[str, Any]):
        """Añade un error al historial para análisis contextual futuro."""
        if job_name not in self.error_history:
            self.error_history[job_name] = []
        
        # Añadir timestamp si no existe
        if 'timestamp' not in error_data:
            error_data['timestamp'] = datetime.datetime.now().isoformat()
        
        self.error_history[job_name].append(error_data)
        
        # Mantener solo los últimos 20 errores por job para evitar crecimiento excesivo
        if len(self.error_history[job_name]) > 20:
            self.error_history[job_name] = self.error_history[job_name][-20:]
    
    def get_job_context(self, job_name: str) -> Dict[str, Any]:
        """Obtiene el contexto completo de un job específico."""
        job_info = self.job_metadata.get(job_name, {})
        system_name = job_info.get('system', 'unknown')
        system_info = self.system_context.get(system_name, {})
        
        # Combinar información de sistema y job
        context = {
            "job_name": job_name,
            "system": system_name,
            "environment": system_info.get('environment', 'unknown'),
            "criticality": job_info.get('criticality', 'medium'),
            "business_impact": job_info.get('business_impact', ''),
            "dependencies": job_info.get('dependencies', []),
            "technical_contact": system_info.get('technical_contact', ''),
            "business_contact": system_info.get('business_contact', ''),
            "error_frequency": self._calculate_error_frequency(job_name)
        }
        
        return context
    
    def _calculate_error_frequency(self, job_name: str) -> Dict[str, Any]:
        """Calcula la frecuencia de errores para un job específico."""
        if job_name not in self.error_history or not self.error_history[job_name]:
            return {"total": 0, "last_24h": 0, "recurrent_patterns": []}
        
        errors = self.error_history[job_name]
        now = datetime.datetime.now()
        
        # Contar errores en las últimas
        last_24h = 0
        error_types = {}
        
        for error in errors:
            # Contar errores por tipo
            error_type = error.get('type', 'unknown')
            if error_type not in error_types:
                error_types[error_type] = 0
            error_types[error_type] += 1
            
            # Contar errores recientes
            try:
                error_time = datetime.datetime.fromisoformat(error.get('timestamp', ''))
                if (now - error_time).total_seconds() < 86400:  # 24 horas en segundos
                    last_24h += 1
            except (ValueError, TypeError):
                pass
        
        # Identificar patrones recurrentes (más de 2 ocurrencias)
        recurrent_patterns = [
            {"type": k, "count": v} 
            for k, v in error_types.items() 
            if v >= 2
        ]
        
        return {
            "total": len(errors),
            "last_24h": last_24h,
            "recurrent_patterns": recurrent_patterns
        }
    
    def analyze_dependencies(self, job_name: str) -> List[Dict[str, Any]]:
        """Analiza las dependencias de un job y su posible relación con errores."""
        job_info = self.job_metadata.get(job_name, {})
        dependencies = job_info.get('dependencies', [])
        results = []
        
        for dep in dependencies:
            # En un sistema real, aquí se consultaría el estado de la dependencia
            # Para este ejemplo, generamos información ficticia
            dep_info = {
                "name": dep,
                "status": "unknown",
                "possible_cause": False,
                "recommendation": ""
            }
            
            # Simulamos análisis basado en el tipo de dependencia
            if dep == "database":
                dep_info["status"] = "operational"
                if any("database" in str(e.get('log', '')).lower() for e in self.error_history.get(job_name, [])):
                    dep_info["possible_cause"] = True
                    dep_info["recommendation"] = "Verificar conexión a base de datos y permisos"
            
            elif dep == "file_storage":
                dep_info["status"] = "operational"
                if any("file" in str(e.get('log', '')).lower() for e in self.error_history.get(job_name, [])):
                    dep_info["possible_cause"] = True
                    dep_info["recommendation"] = "Comprobar acceso al almacenamiento de archivos"
            
            results.append(dep_info)
        
        return results
    
    def contextualize_message(self, 
                             message: str,
                             job_name: str,
                             audience_type: AudienceType,
                             include_history: bool = True) -> str:
        """Adapta un mensaje según el contexto y audiencia."""
        job_context = self.get_job_context(job_name)
        env = job_context.get('environment', 'unknown')
        criticality = job_context.get('criticality', 'medium')
        
        # Base del mensaje contextualizado
        contextualized = message
        
        # Adaptaciones según el entorno
        if env == Environment.PRODUCTION.value:
            if criticality in ['high', 'critical']:
                contextualized = f"[URGENTE] {contextualized}"
        
        # Adaptaciones según la audiencia
        if audience_type == AudienceType.ENGINEER:
            # Para ingenieros, incluir detalles técnicos y contexto de errores previos
            if include_history and job_name in self.error_history:
                similar_errors = self._find_similar_errors(job_name, message)
                if similar_errors:
                    last_error = similar_errors[0]
                    contextualized += f"\n\nNota: Error similar ocurrió {len(similar_errors)} veces anteriormente. "
                    contextualized += f"Última ocurrencia: {last_error.get('timestamp', 'fecha desconocida')}."
            
            # Incluir información de dependencias
            dependencies = self.analyze_dependencies(job_name)
            problem_deps = [d for d in dependencies if d['possible_cause']]
            if problem_deps:
                contextualized += "\n\nPosibles dependencias relacionadas con el error:"
                for dep in problem_deps:
                    contextualized += f"\n- {dep['name']}: {dep['recommendation']}"
        
        elif audience_type == AudienceType.SUPPORT:
            # Para soporte, balancear detalles técnicos con lenguaje más accesible
            if criticality in ['high', 'critical']:
                contextualized += f"\n\nEste es un job {criticality} que afecta al sistema {job_context.get('system', 'desconocido')}."
                contextualized += f"\nImpacto en negocio: {job_context.get('business_impact', 'No especificado')}"
            
            # Añadir información de contacto técnico
            if job_context.get('technical_contact'):
                contextualized += f"\n\nContacto técnico: {job_context.get('technical_contact')}"
        
        elif audience_type == AudienceType.BUSINESS:
            # Para personal de negocio, eliminar tecnicismos y enfocarse en impacto
            # Simplificar el mensaje eliminando detalles técnicos
            contextualized = re.sub(r'Error: .*?:', 'Error:', contextualized)
            contextualized = re.sub(r'\b(?:exception|stack trace|null pointer|undefined|traceback)\b', 'error técnico', contextualized, flags=re.IGNORECASE)
            
            # Añadir información de impacto
            if job_context.get('business_impact'):
                contextualized = f"Se ha detectado un problema que afecta: {job_context.get('business_impact')}.\n\n{contextualized}"
            
            # Añadir información de frecuencia para dar contexto
            frequency = job_context.get('error_frequency', {})
            if frequency.get('total', 0) > 1:
                contextualized += f"\n\nEste problema ha ocurrido {frequency.get('total')} veces, {frequency.get('last_24h')} en las últimas 24 horas."
        
        elif audience_type == AudienceType.CLIENT:
            # Para clientes, mensaje simple, sin tecnicismos, enfocado en solución
            # Eliminar todos los detalles técnicos
            contextualized = re.sub(r'(?:Error|Exception|Warning): .*?[.:\n]', 'Se ha detectado un problema.', contextualized)
            contextualized = re.sub(r'\b(?:database|server|API|endpoint|query|script|function|method|parameter|argument|variable|null|undefined|traceback|stack trace)\b', 'componente del sistema', contextualized, flags=re.IGNORECASE)
            
            # Mensaje orientado a solución
            if criticality in ['high', 'critical']:
                contextualized = f"Estamos trabajando en resolver un problema que afecta el servicio.\n\n{contextualized}"
            else:
                contextualized = f"Hemos detectado un problema menor que estamos resolviendo.\n\n{contextualized}"
                
            # Añadir estimación si es posible
            if job_name in self.error_history:
                contextualized += "\n\nNuestro equipo técnico ya está trabajando en la solución."
        
        return contextualized
    
    def _find_similar_errors(self, job_name: str, message: str) -> List[Dict[str, Any]]:
        """Encuentra errores similares en el historial basado en coincidencia de palabras clave."""
        if job_name not in self.error_history:
            return []
        
        # Extraer palabras clave del mensaje actual (simpificado)
        keywords = set(re.findall(r'\b\w+\b', message.lower()))
        keywords = {w for w in keywords if len(w) > 3}  # filtrar palabras cortas
        
        similar_errors = []
        for error in sorted(self.error_history[job_name], key=lambda x: x.get('timestamp', ''), reverse=True):
            error_text = error.get('log', '') or error.get('message', '')
            error_keywords = set(re.findall(r'\b\w+\b', error_text.lower()))
            error_keywords = {w for w in error_keywords if len(w) > 3}
            
            # Calcular similitud simple basada en palabras compartidas
            if keywords and error_keywords:
                overlap = len(keywords.intersection(error_keywords)) / len(keywords)
                if overlap > 0.5:  # Si comparten más del 50% de palabras clave
                    similar_errors.append(error)
        
        return similar_errors
    
    def generate_context_aware_response(self, 
                                       job_name: str, 
                                       error_data: Dict[str, Any],
                                       audience_type: AudienceType) -> Dict[str, str]:
        """Genera una respuesta completa adaptada al contexto y audiencia."""
        error_type = error_data.get('type', 'unknown')
        error_message = error_data.get('message', 'Error no especificado')
        log_text = error_data.get('log', '')
        
        job_context = self.get_job_context(job_name)
        environment = job_context.get('environment', 'unknown')
        criticality = job_context.get('criticality', 'medium')
        
        # Base de la respuesta
        base_response = {
            'title': f"Error en {job_name}",
            'message': error_message,
            'status': 'investigating',
            'next_steps': []
        }
        
        # Personalización según tipo de error
        if error_type == 'column_mismatch':
            base_response['title'] = f"Error de formato en archivo"
            base_response['message'] = "El formato del archivo no coincide con lo esperado."
            base_response['next_steps'] = ["Verificar columnas del archivo", "Utilizar plantilla correcta"]
        
        elif error_type == 'encoding_error':
            base_response['title'] = f"Error de codificación en archivo"
            base_response['message'] = "La codificación del archivo no es compatible."
            base_response['next_steps'] = ["Guardar archivo en formato UTF-8", "Eliminar caracteres especiales"]
        
        elif error_type == 'connection_error':
            base_response['title'] = f"Error de conexión"
            base_response['message'] = "No se pudo establecer conexión con un servicio requerido."
            base_response['next_steps'] = ["Verificar conectividad de red", "Comprobar credenciales"]
        
        # Ajustar según entorno
        if environment == Environment.PRODUCTION.value:
            if criticality in ['high', 'critical']:
                base_response['status'] = 'critical'
                if audience_type != AudienceType.CLIENT:
                    base_response['title'] = f"URGENTE: {base_response['title']}"
            
            # En producción, ser más conservador con los mensajes para clientes
            if audience_type == AudienceType.CLIENT:
                base_response['message'] = base_response['message'].replace("Error", "Problema")
        
        elif environment == Environment.DEVELOPMENT.value:
            # En desarrollo, incluir más detalles técnicos para todos excepto clientes
            if audience_type != AudienceType.CLIENT:
                base_response['message'] += "\n\nEsto es un entorno de desarrollo."
                if log_text:
                    base_response['message'] += f"\n\nDetalles del log:\n{log_text[:200]}..."
        
        # Añadir recomendaciones específicas según audiencia
        if audience_type == AudienceType.ENGINEER:
            frequency = job_context.get('error_frequency', {})
            deps = self.analyze_dependencies(job_name)
            problem_deps = [d for d in deps if d['possible_cause']]
            
            if frequency.get('total', 0) > 1:
                base_response['message'] += f"\n\nEste error ha ocurrido {frequency.get('total')} veces en total."
                
            if problem_deps:
                base_response['next_steps'] = [f"Revisar {d['name']}: {d['recommendation']}" for d in problem_deps] + base_response['next_steps']
        
        elif audience_type == AudienceType.SUPPORT:
            # Para soporte, añadir referencias a documentación
            base_response['message'] += f"\n\nReferencia: Ver documentación del sistema {job_context.get('system', 'desconocido')}."
            
            if job_context.get('error_frequency', {}).get('recurrent_patterns'):
                patterns = job_context['error_frequency']['recurrent_patterns']
                pattern_str = ", ".join([f"{p['type']} ({p['count']} veces)" for p in patterns])
                base_response['message'] += f"\n\nPatrones recurrentes: {pattern_str}"
        
        elif audience_type == AudienceType.BUSINESS:
            # Para negocio, enfocarse en impacto y timeline
            base_response['title'] = base_response['title'].replace("Error", "Incidencia")
            if job_context.get('business_impact'):
                base_response['message'] = f"Impacto: {job_context.get('business_impact')}\n\n{base_response['message']}"
            
            base_response['next_steps'] = ["Se está trabajando en la solución", "Recibirá actualizaciones periódicas"]
        
        elif audience_type == AudienceType.CLIENT:
            # Para clientes, mensaje simple y orientado a solución
            base_response['title'] = base_response['title'].replace("Error", "Incidencia")
            base_response['message'] = re.sub(r'(?:Error|Exception|Warning).*?[.:\n]', '', base_response['message'])
            base_response['message'] = "Estamos al tanto de esta situación y trabajando para resolverla lo antes posible."
            
            base_response['next_steps'] = ["Nuestro equipo técnico está trabajando en la solución", 
                                           "No es necesario realizar ninguna acción de su parte"]
        
        # Contextualizar el mensaje final
        base_response['message'] = self.contextualize_message(base_response['message'], job_name, audience_type)
        
        return base_response


# Función para integrar con el sistema principal
def get_context_analyzer():
    """Retorna una instancia del analizador de contexto"""
    analyzer = ContextAnalyzer()
    analyzer.load_system_context()
    return analyzer


if __name__ == "__main__":
    # Test básico del analizador de contexto
    analyzer = ContextAnalyzer()
    analyzer.load_system_context()
    
    # Añadir algunos errores de prueba
    test_error = {
        "type": "connection_error",
        "message": "No se pudo conectar a la base de datos",
        "log": "Error: Could not connect to database at 10.0.1.5:3306. Connection timed out."
    }
    analyzer.add_error_to_history("nightly_import", test_error)
    
    # Probar contextualización para diferentes audiencias
    for audience in AudienceType:
        print(f"\n===== Mensaje para {audience.value} =====")
        response = analyzer.generate_context_aware_response("nightly_import", test_error, audience)
        print(f"Título: {response['title']}")
        print(f"Mensaje: {response['message']}")
        print("Pasos siguientes:")
        for step in response['next_steps']:
            print(f"- {step}")
        print("="*40) 