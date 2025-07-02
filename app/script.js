const arquivo = document.getElementById("arquivo");
const tabela = document.getElementById("tabela");

function upload() {
    const file = arquivo.files[0];
    if (file) {
        const formData = new FormData();
        formData.append("file", file);

        fetch("http://localhost:9090/api/upload", {
            method: "POST",
            body: formData
        })
            .then(response => {
                if (response.ok) {
                    alert("Arquivo enviado com sucesso!");
                    fetchAndDisplayFiles();
                } else {
                    alert("Erro ao enviar o arquivo.");
                }
            })
            .catch(error => console.error("Erro ao enviar o arquivo:", error));
        arquivo.value = "";
    } else {
        alert("Por favor, selecione um arquivo para enviar.");
    }
}

function fetchAndDisplayFiles() {
    fetch("http://localhost:9090/api", {
        method: "GET"
    }).then(response => response.json())
        .then(data => {
            data.forEach(item => {
                const tr = document.createElement("tr");
                const id = document.createElement("td");
                const name = document.createElement("td");
                const type = document.createElement("td");
                const createdAt = document.createElement("td");
                const expirationTime = document.createElement("td");
                const botao = document.createElement("td");

                const button = document.createElement("button");
                button.textContent = "Baixar";
                button.onclick = () => {
                    fetch(`http://localhost:9090/api/download?id=${item.id}`, {
                        method: "GET"
                    }).then(response => {
                        if (response.ok) {
                            return response.blob();
                        } else {
                            throw new Error("Erro ao baixar o arquivo");
                        }
                    }).then(blob => {
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = item.name;
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                        window.URL.revokeObjectURL(url);
                    }).catch(error => console.error("Erro ao baixar o arquivo:", error));
                };

                
                id.textContent = item.id;
                name.textContent = item.name;
                type.textContent = item.type;
                createdAt.textContent = item.createdAt;
                expirationTime.textContent = item.expirationTime;
                
                tr.appendChild(id);
                tr.appendChild(name);
                tr.appendChild(type);
                tr.appendChild(createdAt);
                tr.appendChild(expirationTime);
                botao.appendChild(button);
                tr.appendChild(botao);
                tabela.appendChild(tr);
            });
        })
        .catch(error => console.error("Erro ao buscar a lista:", error));
}

fetchAndDisplayFiles();

setTimeout(() => {
    fetchAndDisplayFiles();
}, 30000);
