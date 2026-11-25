const elementoDados = document.getElementById('dados-mes');
const canvas = document.getElementById('graf');

if (elementoDados && canvas) {
    const dados = JSON.parse(
        elementoDados.textContent
    );

    new Chart(canvas, {
        type: 'bar',
        data: {
            labels: dados.map(d => d.mes),
            datasets: [{
                label: 'Livros cadastrados por mês',
                data: dados.map(d => d.total)
            }]
        }
    });
}
