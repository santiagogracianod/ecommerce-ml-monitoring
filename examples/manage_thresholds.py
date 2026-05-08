"""
Script de ejemplo para gestionar thresholds de alertas dinámicamente.
Este script demuestra cómo actualizar los umbrales sin reiniciar el servicio.
"""
import requests
import json
import time
from datetime import datetime


# Configuración
BASE_URL = "http://localhost:8003/api/v1"
THRESHOLDS_URL = f"{BASE_URL}/alerts/config/thresholds"
INVALIDATE_CACHE_URL = f"{BASE_URL}/alerts/config/thresholds/invalidate-cache"


def print_separator():
    """Imprimir separador visual."""
    print("\n" + "=" * 80 + "\n")


def get_current_config(service_name=None):
    """Obtener configuración actual de thresholds."""
    print("📊 Obteniendo configuración actual...")

    params = {}
    if service_name:
        params["service_name"] = service_name

    try:
        response = requests.get(THRESHOLDS_URL, params=params)
        response.raise_for_status()

        config = response.json()

        print("\n✅ Configuración actual:")
        print(f"   • Drift threshold: {config['drift_threshold']}")
        print(f"   • Confidence drop threshold: {config['confidence_drop_threshold']}")
        print(f"   • Latency threshold: {config['latency_threshold_ms']} ms")
        print(f"   • Error rate threshold: {config['error_rate_threshold']}")
        print(f"   • Última actualización: {config['updated_at']}")
        print(f"   • Actualizado por: {config.get('updated_by', 'N/A')}")

        if config.get('service_overrides'):
            print(f"\n   📝 Service overrides:")
            for service, overrides in config['service_overrides'].items():
                print(f"      {service}:")
                for key, value in overrides.items():
                    print(f"         - {key}: {value}")

        return config

    except requests.exceptions.RequestException as e:
        print(f"❌ Error al obtener configuración: {e}")
        return None


def update_threshold(
    drift_threshold=None,
    confidence_drop_threshold=None,
    latency_threshold_ms=None,
    error_rate_threshold=None,
    service_overrides=None,
    description=None,
    updated_by="admin"
):
    """Actualizar thresholds."""
    print(f"⚙️  Actualizando thresholds...")

    # Preparar payload (solo campos no nulos)
    payload = {}
    if drift_threshold is not None:
        payload["drift_threshold"] = drift_threshold
    if confidence_drop_threshold is not None:
        payload["confidence_drop_threshold"] = confidence_drop_threshold
    if latency_threshold_ms is not None:
        payload["latency_threshold_ms"] = latency_threshold_ms
    if error_rate_threshold is not None:
        payload["error_rate_threshold"] = error_rate_threshold
    if service_overrides is not None:
        payload["service_overrides"] = service_overrides
    if description is not None:
        payload["description"] = description

    payload["updated_by"] = updated_by

    print(f"\n📤 Enviando cambios:")
    print(json.dumps(payload, indent=2))

    try:
        response = requests.put(
            THRESHOLDS_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()

        config = response.json()

        print(f"\n✅ Thresholds actualizados exitosamente!")
        print(f"   • Nueva configuración guardada")
        print(f"   • Actualizado por: {config.get('updated_by')}")
        print(f"   • Timestamp: {config['updated_at']}")

        return config

    except requests.exceptions.RequestException as e:
        print(f"❌ Error al actualizar thresholds: {e}")
        if hasattr(e.response, 'text'):
            print(f"   Detalle: {e.response.text}")
        return None


def invalidate_cache():
    """Invalidar caché para aplicar cambios inmediatamente."""
    print("🔄 Invalidando caché...")

    try:
        response = requests.post(INVALIDATE_CACHE_URL)
        response.raise_for_status()

        result = response.json()
        print(f"✅ {result['message']}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Error al invalidar caché: {e}")


def demo_basic_update():
    """Demostración: Actualización básica de drift threshold."""
    print_separator()
    print("🎯 DEMO 1: Actualización básica de drift threshold")
    print_separator()

    # Mostrar configuración actual
    get_current_config()

    print_separator()

    # Actualizar drift threshold
    update_threshold(
        drift_threshold=0.25,
        description="Demo: Reducir threshold para mayor sensibilidad",
        updated_by="demo_script"
    )

    print_separator()

    # Invalidar caché
    invalidate_cache()

    print_separator()

    # Verificar cambios
    get_current_config()


def demo_multiple_thresholds():
    """Demostración: Actualizar múltiples thresholds."""
    print_separator()
    print("🎯 DEMO 2: Actualizar múltiples thresholds")
    print_separator()

    update_threshold(
        drift_threshold=0.2,
        latency_threshold_ms=1500,
        error_rate_threshold=0.03,
        description="Demo: Configuración más estricta",
        updated_by="demo_script"
    )

    invalidate_cache()

    time.sleep(1)

    get_current_config()


def demo_service_overrides():
    """Demostración: Configurar overrides por servicio."""
    print_separator()
    print("🎯 DEMO 3: Configurar overrides por servicio")
    print_separator()

    update_threshold(
        service_overrides={
            "search": {
                "drift_threshold": 0.25,
                "latency_threshold_ms": 1500
            },
            "sentiment": {
                "drift_threshold": 0.35,
                "latency_threshold_ms": 2500
            }
        },
        description="Demo: Configuración específica por servicio",
        updated_by="demo_script"
    )

    invalidate_cache()

    print_separator()

    # Mostrar configuración global
    print("📊 Configuración global:")
    get_current_config()

    print_separator()

    # Mostrar configuración para search
    print("📊 Configuración para search service:")
    get_current_config(service_name="search")

    print_separator()

    # Mostrar configuración para sentiment
    print("📊 Configuración para sentiment service:")
    get_current_config(service_name="sentiment")


def demo_restore_defaults():
    """Demostración: Restaurar valores por defecto."""
    print_separator()
    print("🎯 DEMO 4: Restaurar valores por defecto")
    print_separator()

    update_threshold(
        drift_threshold=0.3,
        confidence_drop_threshold=0.1,
        latency_threshold_ms=2000,
        error_rate_threshold=0.05,
        service_overrides=None,
        description="Demo: Restaurar valores por defecto",
        updated_by="demo_script"
    )

    invalidate_cache()

    time.sleep(1)

    get_current_config()


def interactive_menu():
    """Menú interactivo para gestionar thresholds."""
    while True:
        print_separator()
        print("🎮 MENÚ DE GESTIÓN DE THRESHOLDS")
        print_separator()
        print("1. Ver configuración actual")
        print("2. Actualizar drift threshold")
        print("3. Actualizar latency threshold")
        print("4. Actualizar error rate threshold")
        print("5. Configurar overrides por servicio")
        print("6. Invalidar caché")
        print("7. Restaurar valores por defecto")
        print("8. Ejecutar todas las demos")
        print("0. Salir")
        print()

        try:
            choice = input("Selecciona una opción: ").strip()

            if choice == "0":
                print("\n👋 ¡Hasta luego!")
                break

            elif choice == "1":
                print_separator()
                get_current_config()

            elif choice == "2":
                value = float(input("Nuevo drift threshold (0.0 - 1.0): "))
                description = input("Descripción del cambio: ")
                updated_by = input("Tu nombre/usuario: ")

                print_separator()
                update_threshold(
                    drift_threshold=value,
                    description=description,
                    updated_by=updated_by
                )
                invalidate_cache()

            elif choice == "3":
                value = int(input("Nuevo latency threshold (ms): "))
                description = input("Descripción del cambio: ")
                updated_by = input("Tu nombre/usuario: ")

                print_separator()
                update_threshold(
                    latency_threshold_ms=value,
                    description=description,
                    updated_by=updated_by
                )
                invalidate_cache()

            elif choice == "4":
                value = float(input("Nuevo error rate threshold (0.0 - 1.0): "))
                description = input("Descripción del cambio: ")
                updated_by = input("Tu nombre/usuario: ")

                print_separator()
                update_threshold(
                    error_rate_threshold=value,
                    description=description,
                    updated_by=updated_by
                )
                invalidate_cache()

            elif choice == "5":
                demo_service_overrides()

            elif choice == "6":
                print_separator()
                invalidate_cache()

            elif choice == "7":
                demo_restore_defaults()

            elif choice == "8":
                demo_basic_update()
                time.sleep(2)
                demo_multiple_thresholds()
                time.sleep(2)
                demo_service_overrides()
                time.sleep(2)
                demo_restore_defaults()

            else:
                print("❌ Opción inválida")

        except KeyboardInterrupt:
            print("\n\n👋 ¡Hasta luego!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


def main():
    """Función principal."""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║  🎛️  Gestor de Thresholds de Alertas - ML Monitoring        ║
    ║                                                               ║
    ║  Este script te permite actualizar los umbrales de alertas   ║
    ║  dinámicamente sin reiniciar el servicio.                    ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    # Verificar conexión con el servicio
    print("🔍 Verificando conexión con el servicio de monitoreo...")
    try:
        response = requests.get(f"{BASE_URL.replace('/api/v1', '')}/health", timeout=5)
        response.raise_for_status()
        print("✅ Servicio de monitoreo disponible")
    except requests.exceptions.RequestException as e:
        print(f"❌ No se pudo conectar al servicio de monitoreo")
        print(f"   Asegúrate de que el servicio esté ejecutándose en {BASE_URL}")
        print(f"   Error: {e}")
        return

    # Mostrar menú interactivo
    interactive_menu()


if __name__ == "__main__":
    main()
