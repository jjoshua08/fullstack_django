const dados = JSON.parse(
    document.getElementById('dados-mes').textContent
);

new Chart(document.getElementById('graf'), {
    type: 'bar',
    data: {
        labels: dados.map(d => d.mes),
        datasets: [{
            label: 'Livros cadastrados por mês',
            data: dados.map(d => d.total)
        }]
    }
});
