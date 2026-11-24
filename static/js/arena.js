'use strict';

const arena = document.querySelector('.arena');
const rutas = arena.dataset;
const formulario = document.querySelector('#combate-form');
const selectores = [...formulario.querySelectorAll('select')];
const boton = document.querySelector('#predecir');
const estado = document.querySelector('#estado-combate');
const reintentar = document.querySelector('#reintentar');
const catalogo = new Map();
const stats = { ataque: 'Ataque', defensa: 'Defensa', velocidad: 'Velocidad', salud: 'Salud' };
const decimal = new Intl.NumberFormat('es', { maximumFractionDigits: 2 });
const porcentaje = new Intl.NumberFormat('es', { style: 'percent', maximumFractionDigits: 1 });
const hora = new Intl.DateTimeFormat('es', { dateStyle: 'short', timeStyle: 'medium' });
let consultaHistorial;

const tarjetaCronica = document.querySelector('.arena-cronica');
const avisoCronica = document.querySelector('#estado-cronica');
const lineasCronica = document.querySelector('#lineas-cronica');
const pedirCronica = document.querySelector('#pedir-cronica');
let dueloCronica;
let temporizadorCronica;

function cambiarCronica(respuesta) {
    dueloCronica?.control.abort();
    clearTimeout(temporizadorCronica);
    const id = respuesta?.headers.get('X-Combat-Log-Id');
    const referencia = respuesta?.headers.get('X-Combate-Referencia');
    dueloCronica = id && referencia ? {
        url: tarjetaCronica.dataset.url.replace('/0/', '/' + id + '/'),
        referencia, control: new AbortController(), metodo: 'POST',
    } : null;
    lineasCronica.replaceChildren();
    pedirCronica.hidden = !dueloCronica;
    pedirCronica.disabled = false;
    pedirCronica.textContent = 'Generar crónica';
    avisoCronica.textContent = dueloCronica ? 'Puedes narrar esta predicción con IA.'
        : 'Predice un combate para solicitar su crónica.';
}

function segundosEspera(valor) {
    if (!valor) return 0;
    const segundos = /^\d+$/.test(valor) ? Number(valor) : Math.ceil((Date.parse(valor) - Date.now()) / 1000);
    return Number.isFinite(segundos) ? Math.max(1, segundos) : 0;
}

function permitirReintento(duelo, mensaje, espera) {
    avisoCronica.textContent = mensaje + (espera ? ' Vuelve a intentarlo en ' + espera + ' s.' : '');
    pedirCronica.textContent = duelo.metodo === 'GET' ? 'Consultar estado' : 'Reintentar crónica';
    pedirCronica.hidden = false;
    pedirCronica.disabled = Boolean(espera);
    if (espera) temporizadorCronica = setTimeout(() => { pedirCronica.disabled = false; }, espera * 1000);
}

async function solicitarCronica(duelo) {
    if (!duelo || duelo !== dueloCronica) return;
    pedirCronica.disabled = true;
    avisoCronica.textContent = 'Preparando la crónica…';
    try {
        const respuesta = await fetch(duelo.url, {
            method: duelo.metodo, headers: { 'X-Combate-Referencia': duelo.referencia },
            signal: duelo.control.signal, cache: 'no-store',
        });
        const datos = await respuesta.json();
        if (duelo !== dueloCronica) return;
        const espera = segundosEspera(respuesta.headers.get('Retry-After'));
        if (respuesta.status === 202) {
            duelo.metodo = 'GET';
            temporizadorCronica = setTimeout(() => solicitarCronica(duelo), (espera || 2) * 1000);
            return;
        }
        if (datos.estado === 'lista') {
            lineasCronica.replaceChildren(...datos.lineas.map(texto => elemento('p', texto)));
            avisoCronica.textContent = 'Crónica de la predicción';
        } else if (datos.estado === 'no_configurada') {
            avisoCronica.textContent = 'La narración con IA está desactivada en esta demo.';
        } else if (respuesta.status === 429) {
            if (datos.estado === 'cuota') duelo.metodo = 'POST';
            permitirReintento(duelo, 'Se alcanzó el límite de crónicas.', espera);
            return;
        } else if (datos.reintentable) {
            duelo.metodo = 'POST';
            permitirReintento(duelo, 'El narrador no pudo completar esta crónica.', espera);
            return;
        } else {
            avisoCronica.textContent = datos.estado === 'referencia_invalida' ? 'La referencia al combate ha caducado.'
                : 'La crónica no está disponible para este combate.';
        }
        pedirCronica.hidden = true;
    } catch {
        if (duelo !== dueloCronica) return;
        // El servidor pudo haber aceptado el POST. Consultar antes de repetirlo.
        duelo.metodo = 'GET';
        permitirReintento(duelo, 'No pudimos confirmar el estado de la crónica.', 0);
    }
}

pedirCronica.addEventListener('click', () => solicitarCronica(dueloCronica));

function elemento(tag, texto) {
    const nodo = document.createElement(tag);
    nodo.textContent = texto;
    return nodo;
}

function dibujarComparativa(primero, segundo) {
    document.querySelector('#nombre-1').textContent = primero?.nombre ?? 'Luchador 1';
    document.querySelector('#nombre-2').textContent = segundo?.nombre ?? 'Luchador 2';
    const filas = [];
    for (const [stat, etiqueta] of Object.entries(stats)) {
        const fila = document.createElement('div');
        fila.className = 'arena-estadistica';
        const valores = document.createElement('div');
        valores.className = 'arena-valores';
        valores.append(elemento('strong', primero?.[stat] ?? '—'), elemento('span', etiqueta),
            elemento('strong', segundo?.[stat] ?? '—'));
        const barras = document.createElement('div');
        barras.className = 'arena-barras';
        barras.setAttribute('aria-hidden', 'true');
        const maximo = Math.max(1, primero?.[stat] ?? 0, segundo?.[stat] ?? 0);
        for (const criatura of [primero, segundo]) {
            const pista = document.createElement('span');
            pista.className = 'arena-pista';
            const barra = document.createElement('i');
            barra.style.width = Math.max(0, (criatura?.[stat] ?? 0) / maximo * 100) + '%';
            pista.append(barra);
            barras.append(pista);
        }
        fila.append(valores, barras);
        filas.push(fila);
    }
    document.querySelector('#comparativa').replaceChildren(...filas);
}

function actualizarSeleccion() {
    cambiarCronica();
    const pareja = selectores.map(select => catalogo.get(select.value));
    selectores.forEach((select, i) => {
        const criatura = pareja[i];
        const tarjeta = select.closest('.arena-criatura');
        tarjeta.classList.remove('es-ganador');
        tarjeta.querySelector('.arena-tipo').textContent = [criatura?.tipo_primario, criatura?.tipo_secundario].filter(Boolean).join(' / ');
        const imagen = tarjeta.querySelector('img');
        const inicial = tarjeta.querySelector('.arena-retrato span');
        inicial.textContent = criatura?.nombre.charAt(0) || '—';
        inicial.hidden = Boolean(criatura?.imagen);
        imagen.hidden = !criatura?.imagen;
        if (criatura?.imagen) imagen.src = criatura.imagen;
        else imagen.removeAttribute('src');
    });
    dibujarComparativa(...pareja);
    document.querySelector('#inferencia').hidden = true;
    document.querySelector('#inferencia-vacia').hidden = false;
    const repetida = pareja[0] && pareja[0] === pareja[1];
    boton.disabled = !pareja.every(Boolean) || repetida;
    estado.textContent = repetida ? 'Elige dos criaturas distintas.' : '';
}

async function cargarCatalogo() {
    try {
        const respuesta = await fetch(rutas.catalogo);
        if (!respuesta.ok) throw new Error();
        const criaturas = await respuesta.json();
        for (const criatura of criaturas) {
            catalogo.set(String(criatura.id), criatura);
            for (const select of selectores) {
                const opcion = elemento('option', criatura.nombre);
                opcion.value = criatura.id;
                select.append(opcion);
            }
        }
        selectores.forEach((select, i) => {
            select.disabled = catalogo.size === 0;
            select.value = String(criaturas[i]?.id ?? '');
        });
        actualizarSeleccion();
        if (catalogo.size < 2) estado.textContent = 'Se necesitan dos criaturas en el catálogo para predecir.';
    } catch {
        estado.textContent = 'No pudimos cargar las criaturas. Recarga la página para volver a intentar.';
    }
}

function mostrarPrediccion({ resultado, metricas }) {
    document.querySelector('#ganador').textContent = resultado.ganador_nombre;
    document.querySelector('#confianza').textContent = resultado.probabilidad.replace('.', ',');
    document.querySelector('#latencia').textContent = decimal.format(metricas.latencia_ms) + ' ms';
    const diferencias = Object.entries(stats).map(([stat, nombre]) => {
        const valor = metricas.diferencial[stat];
        const texto = valor == null ? 'Sin dato' : (valor > 0 ? '+' : '') + valor;
        return elemento('span', nombre + ' ' + texto);
    });
    document.querySelector('#diferencial').replaceChildren(...diferencias);
    const ventajas = selectores.map((select, i) => {
        const factor = metricas.ventaja_elemental['luchador_' + (i + 1)];
        select.closest('.arena-criatura').classList.toggle('es-ganador', Number(select.value) === resultado.ganador_id);
        return elemento('span', catalogo.get(select.value).nombre + ' ×' + decimal.format(factor));
    });
    document.querySelector('#ventaja').replaceChildren(...ventajas);
    document.querySelector('#inferencia-vacia').hidden = true;
    document.querySelector('#inferencia').hidden = false;
    estado.textContent = 'Ganador predicho: ' + resultado.ganador_nombre + '.';
}

function mensajeLimite(reintento) {
    const base = 'Alcanzaste el límite de predicciones. ';
    if (!reintento) return base + 'Espera un momento y vuelve a intentarlo.';
    const segundos = segundosEspera(reintento);
    if (!segundos) return base + 'Espera un momento y vuelve a intentarlo.';
    return base + 'Vuelve a intentarlo en ' + segundos + ' s.';
}

async function predecir(evento) {
    evento.preventDefault();
    if (boton.disabled) return;
    cambiarCronica();
    boton.disabled = true;
    for (const select of selectores) select.disabled = true;
    estado.textContent = 'Calculando predicción…';
    try {
        const respuesta = await fetch(rutas.predecir, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ luchador_1_id: selectores[0].value, luchador_2_id: selectores[1].value }),
        });
        if (respuesta.status === 429) {
            estado.textContent = mensajeLimite(respuesta.headers.get('Retry-After'));
            return;
        }
        const datos = await respuesta.json();
        if (!respuesta.ok) {
            estado.textContent = datos.detail || datos.error || 'No pudimos completar la predicción.';
            return;
        }
        mostrarPrediccion(datos);
        cambiarCronica(respuesta);
        cargarHistorial();
    } catch {
        estado.textContent = 'No pudimos confirmar la respuesta del Oráculo. Consulta el historial.';
    } finally {
        boton.disabled = false;
        for (const select of selectores) select.disabled = false;
    }
}

async function cargarHistorial() {
    consultaHistorial?.abort();
    const consulta = new AbortController();
    consultaHistorial = consulta;
    const aviso = document.querySelector('#estado-historial');
    aviso.textContent = 'Actualizando historial…';
    reintentar.hidden = true;
    try {
        const respuesta = await fetch(rutas.historial, { signal: consulta.signal, cache: 'no-store' });
        if (!respuesta.ok) throw new Error();
        const { combates } = await respuesta.json();
        const nombre = criatura => criatura?.nombre ?? 'Criatura eliminada';
        const filas = combates.map(combate => {
            const fila = document.createElement('tr');
            for (const valor of [
                hora.format(new Date(combate.creado_en)),
                nombre(combate.luchador_1) + ' vs. ' + nombre(combate.luchador_2),
                nombre(combate.ganador_predicho), porcentaje.format(combate.probabilidad),
                decimal.format(combate.metricas.latencia_ms) + ' ms',
            ]) fila.append(elemento('td', valor));
            return fila;
        });
        if (consulta.signal.aborted) return;
        document.querySelector('#filas-combates').replaceChildren(...filas);
        aviso.textContent = filas.length ? '' : 'Aún no se han registrado predicciones.';
    } catch {
        if (consulta.signal.aborted) return;
        aviso.textContent = 'No se pudo actualizar el historial.';
        reintentar.hidden = false;
    }
}

for (const select of selectores) {
    select.addEventListener('change', actualizarSeleccion);
    const retrato = select.closest('.arena-criatura').querySelector('img');
    retrato.addEventListener('error', () => {
        retrato.hidden = true;
        retrato.previousElementSibling.hidden = false;
    });
}
formulario.addEventListener('submit', predecir);
reintentar.addEventListener('click', cargarHistorial);
dibujarComparativa();
cargarCatalogo();
cargarHistorial();
