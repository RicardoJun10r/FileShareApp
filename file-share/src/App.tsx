import { useState, useEffect } from 'react';
import { columns_file } from './components/tables/column-table';
import { DataTable } from './components/tables/data-table';
import { Input } from './components/ui/input';
import { Label } from './components/ui/label';
import { Arquivo } from './shared/obj-interface';
import { Button } from './components/ui/button';
import pako from 'pako';
import { io } from 'socket.io-client';

// Configurar a conexão com o Socket.IO
const socket = io('http://localhost:3001');

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [cont, setCont] = useState(0);
  const [data, setData] = useState<Arquivo[]>([]);

  // Função de upload de arquivo
  const handleOnChangeFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setFile(file);
    }
  };

  // Enviar arquivo para o servidor via Socket.IO
  const upload = () => {
    if (file) {
      const reader = new FileReader();

      reader.onload = () => {
        const fileContent = new Uint8Array(reader.result as ArrayBuffer);
        const compressedContent = pako.deflate(fileContent);

        const compressedFile = new File([compressedContent], file.name, {
          type: file.type,
          lastModified: file.lastModified,
        });

        let novo_arquvio: Arquivo = {
          horario: new Date(),
          nome: file.name,
          tamanho: file.size,
          tipo: file.type,
          arquivo: compressedFile,
          contador: 300,
        };

        // Atualizar o estado local
        setCont(prevCont => prevCont + 1);

        // Enviar o arquivo para o servidor
        socket.emit('uploadFile', novo_arquvio);
      };

      reader.readAsArrayBuffer(file);
    }
  };

  useEffect(() => {
    // Ouvir arquivos compartilhados do servidor
    socket.on('sharedFiles', (sharedFiles: Arquivo[]) => {
      setData(sharedFiles);
      setCont(sharedFiles.length);
    });

    // Limpar a conexão ao desmontar o componente
    return () => {
      socket.off('sharedFiles');
    };
  }, []);

  // Adicionar contagem decrescente aos arquivos
  useEffect(() => {
    const intervalId = setInterval(() => {
      setData((prevData) =>
        prevData.map((item) => {
          if (item.contador > 0) {
            return { ...item, contador: item.contador - 1 };
          }
          return item;
        })
      );
    }, 1000);

    return () => clearInterval(intervalId);
  }, [data]);

  return (
    <div className="h-screen w-screen justify-center flex items-center">
      <header className="top-0 fixed bg-slate-500 w-full flex justify-between items-center px-4 py-2">
        <h1 className="text-left">FileShare</h1>
        <p className="text-right">
          Quantidade de Arquivos enviados:
          <span> {cont}</span>
        </p>
      </header>
      <main>
        <div>
          <div className="grid w-full max-w-sm items-center gap-1.5">
            <Label htmlFor="arquivo">Arquivo</Label>
            <Input onChange={handleOnChangeFile} id="arquivo" type="file" />
            <Button onClick={upload}>Upload</Button>
          </div>
          <div className="w-screen">
            <DataTable columns={columns_file} data={data} />
          </div>
        </div>
      </main>
      <footer className="bottom-0 p-4 fixed flex justify-center bg-slate-400 w-full">
        {file && (
          <div className="flex space-x-3">
            <p>Informações do arquivo: </p>
            <p>( Nome: {file.name}</p>
            <p> Tipo: {file.type}</p>
            <p> Tamanho: {file.size} )</p>
          </div>
        )}
      </footer>
    </div>
  );
}

export default App;
