// 1. Traducción Dinámica (SCAMPER: Adaptar)
function translatePage() {
    const title = document.querySelector('h1');
    const btn = document.querySelector('.btn-lang');
    
    if (title.innerText.includes("Herencia")) {
        title.innerText = "Heritage in every fiber";
        btn.innerText = "ES";
        console.log("Idioma cambiado a Inglés");
    } else {
        title.innerText = "Herencia en cada fibra";
        btn.innerText = "EN";
    }
}

// 2. Alerta de Compra con Transparencia
function comprar(nombre, pago) {
    const confirmation = confirm(
        `CERTIFICADO DE TRANSPARENCIA:\n\n` +
        `Estás adquiriendo: ${nombre}\n` +
        `Este acto asegura que S/ ${pago} se entreguen sin intermediarios al maestro.\n\n` +
        `¿Confirmas tu apoyo a la cultura viva?`
    );
    
    if (confirmation) {
        alert("¡Pedido procesado! Gracias por ser parte del cambio.");
    }
}

// 3. Efecto de Feedback en Formularios
document.addEventListener('DOMContentLoaded', () => {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', () => {
            const btn = form.querySelector('button');
            if (btn) {
                btn.innerHTML = "PROCESANDO...";
                btn.style.opacity = "0.7";
                btn.style.pointerEvents = "none";
            }
        });
    });
});

// 4. Previsualización de Imagen (Para el Maestro)
const inputArchivo = document.querySelector('input[type="file"]');
if (inputArchivo) {
    inputArchivo.addEventListener('change', function() {
        const fileName = this.files[0].name;
        console.log("Archivo seleccionado: " + fileName);
        // Aquí podrías añadir lógica para mostrar la miniatura antes de subir
    });
}