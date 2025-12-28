document.addEventListener('DOMContentLoaded', () => {
    cargarSelectores();
});

let todasLasCriaturas = []; // Guardamos copia local para buscar fotos rápido

async function cargarSelectores() {
    // Reutilizamos tu API de criaturas para llenar las listas
    const response = await fetch('/api/criaturas/');
    todasLasCriaturas = await response.json();

    const select1 = document.getElementById('select-luchador-1');
    const select2 = document.getElementById('select-luchador-2');

    todasLasCriaturas.forEach(c => {
        const option = `<option value="${c.id}">${c.nombre}</option>`;
        select1.insertAdjacentHTML('beforeend', option);
        select2.insertAdjacentHTML('beforeend', option);
    });

    // Event Listeners para mostrar la foto cuando seleccionas
    select1.addEventListener('change', (e) => actualizarPreview(e.target.value, 'preview-1'));
    select2.addEventListener('change', (e) => actualizarPreview(e.target.value, 'preview-2'));
}

function actualizarPreview(id, containerId) {
    const container = document.getElementById(containerId);
    if (!id) { container.innerHTML = ''; return; }

    const criatura = todasLasCriaturas.find(c => c.id == parseInt(id));
    if (criatura && criatura.imagen) {
        container.innerHTML = `<img src="${criatura.imagen}" style="width: 100%; border-radius: 10px; margin-top: 10px;">`;
    } else {
        container.innerHTML = '';
    }
}

async function predecirCombate() {
    const id1 = document.getElementById('select-luchador-1').value;
    const id2 = document.getElementById('select-luchador-2').value;
    const resultadoDiv = document.getElementById('resultado-overlay');

    if (!id1 || !id2) {
        resultadoDiv.innerHTML = '<span style="color:red">Selecciona dos luchadores primero.</span>';
        return;
    }

    if (id1 === id2) {
        resultadoDiv.innerHTML = '<span style="color:orange">¡No pueden pelear contra sí mismos!</span>';
        return;
    }

    resultadoDiv.innerHTML = 'Consultando a la IA... 🤖';

    // LLAMADA A TU API DE IA
    try {
        const response = await fetch('/api/oraculo/predecir/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ luchador_1_id: id1, luchador_2_id: id2 })
        });

        const data = await response.json();

        if (data.resultado) {
            resultadoDiv.innerHTML = `
                <span style="color: var(--accent-color); font-size: 30px;">
                    🏆 Ganador: ${data.resultado.ganador_nombre}
                </span>
                <br>
                <span style="font-size: 18px; color: #666;">
                    ${data.resultado.mensaje}
                </span>
            `;
        }
    } catch (error) {
        resultadoDiv.innerText = 'Error al consultar el oráculo.';
    }
}