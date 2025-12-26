/* static/js/app.js */

// Esperamos a que todo el HTML se cargue antes de ejecutar nada.
document.addEventListener('DOMContentLoaded', () => {
    cargarCriaturas();
});

// Función asíncrona: Nos permite esperar (await) a que el servidor responda sin congelar la pantalla.
async function cargarCriaturas() {
    const container = document.getElementById('creature-container');
    
    // URL de tu API (la que probamos antes)
    const url = '/api/criaturas/';

    try {
        // 1. FETCH: "Hola servidor, dame los datos de esta URL"
        const response = await fetch(url);

        // Verificamos si la respuesta fue exitosa (código 200)
        if (!response.ok) {
            throw new Error('Error en la conexión con la API');
        }

        // 2. CONVERSIÓN: Convertimos la respuesta cruda a formato JSON (Arrays y Objetos)
        const criaturas = await response.json();

        // 3. LIMPIEZA: Borramos la tarjeta de "Ejemplo" que pusimos en el HTML
        container.innerHTML = '';

        // 4. BUCLE: Recorremos cada criatura recibida
        criaturas.forEach(criatura => {
            // Creamos el HTML de la tarjeta dinámicamente
            const cardHTML = crearTarjetaHTML(criatura);
            
            // Inyectamos ese HTML dentro del contenedor grid
            container.insertAdjacentHTML('beforeend', cardHTML);
        });

    } catch (error) {
        console.error('Hubo un problema:', error);
        container.innerHTML = '<p class="error-msg">No se pudieron cargar las criaturas.</p>';
    }
}

// Función auxiliar para construir el HTML de una sola tarjeta
function crearTarjetaHTML(criatura) {
    // Si la criatura no tiene imagen, usamos una por defecto (placeholder)
    const imagenUrl = criatura.imagen ? criatura.imagen : 'https://via.placeholder.com/400x300?text=Sin+Imagen';

    // Formateamos los tipos (ej: "Fuego / Plasma")
    let tipos = criatura.tipo_primario.toUpperCase();
    if (criatura.tipo_secundario) {
        tipos += ` / ${criatura.tipo_secundario.toUpperCase()}`;
    }

    // Usamos "Template Literals" (las comillas invertidas `) para mezclar HTML con variables JS
    return `
        <div class="creature-card">
            <img src="${imagenUrl}" alt="${criatura.nombre}" class="card-image" loading="lazy">
            <h3 class="card-title">${criatura.nombre}</h3>
            <span class="card-type">${tipos}</span>
            
            <div class="stats-row">
                <span class="stat-badge">ATQ ${criatura.ataque}</span>
                <span class="stat-badge" style="background: rgba(52, 199, 89, 0.1); color: #34c759;">DEF ${criatura.defensa}</span>
            </div>
        </div>
    `;
}