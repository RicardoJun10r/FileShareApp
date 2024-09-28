import { useState, useEffect } from 'react';
import { columns_file } from './components/tables/column-table';
import { DataTable } from './components/tables/data-table';
import { Input } from './components/ui/input';
import { Label } from './components/ui/label';
import { Arquivo } from './shared/obj-interface';
import { Button } from './components/ui/button';
import pako from 'pako';
import { io } from 'socket.io-client';

const socket = io('http://localhost:3001');

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [data, setData] = useState<Arquivo[]>([]);

  useEffect(() => {
    socket.on('sharedFiles', (sharedFiles: Arquivo[]) => {
      console.log('Recebendo arquivos do servidor:', sharedFiles);

      setData((prevData) => {
        return sharedFiles.map((file) => {
          const existingFile = prevData.find((f) => f.nome === file.nome);
          return {
            ...file,
            contador: existingFile?.contador || 300,
          };
        });
      });
    });

    return () => {
      socket.off('sharedFiles');
    };
  }, []);

  useEffect(() => {
    const intervalId = setInterval(() => {
      setData((prevData) =>
        prevData.map((item) => {
          if (item.contador > 0) {
            return { ...item, contador: item.contador - 1 };
          } else {
            return { ...item, contador: 0 };
          }
        })
      );
    }, 1000);

    return () => {
      clearInterval(intervalId);
    };
  }, []);

  const handleOnChangeFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
    }
  };

  const upload = () => {
    if (file) {
      const reader = new FileReader();

      reader.onload = () => {
        try {
          const fileContent = new Uint8Array(reader.result as ArrayBuffer);
          const compressedContent = pako.deflate(fileContent);

          const base64Data = btoa(
            compressedContent.reduce((data, byte) => data + String.fromCharCode(byte), '')
          );

          const novoArquivo: Arquivo = {
            horario: new Date(),
            nome: file.name,
            tamanho: file.size,
            tipo: file.type,
            arquivo: base64Data,
            contador: 300,
          };

          console.log('Arquivo comprimido pronto para envio:', novoArquivo);

          socket.emit('uploadFile', novoArquivo);

          setData((prevData) => [...prevData, novoArquivo]);
        } catch (err) {
          console.error('Erro ao processar o arquivo:', err);
        }
      };

      reader.onerror = () => {
        console.error('Erro ao ler o arquivo.');
      };

      reader.readAsArrayBuffer(file);
    }
  };

  return (
    <div className='h-screen w-screen justify-center flex items-center'>
      <header className='top-0 fixed bg-slate-500 w-full flex justify-between items-center px-4 py-2'>
        <h1 className='text-left'>FileShare</h1>
        <p className='text-right'>
          Quantidade de Arquivos enviados: <span>{data.length}</span>
        </p>
      </header>
      <main>
        <div>
          <div className='grid w-full max-w-sm items-center gap-1.5'>
            <Label htmlFor='arquivo'>Arquivo</Label>
            <Input onChange={handleOnChangeFile} id='arquivo' type='file' />
            <Button onClick={upload}>Upload</Button>
          </div>
          <div className='w-screen'>
            <DataTable columns={columns_file} data={data} />
          </div>
        </div>
      </main>
      <footer className='bottom-0 p-4 fixed flex justify-center bg-slate-400 w-full'>
        {file && (
          <div className='flex space-x-3'>
            <p>Informações do arquivo: </p>
            <p>( Nome: {file.name} </p>
            <p> Tipo: {file.type} </p>
            <p> Tamanho: {file.size} )</p>
          </div>
        )}
      </footer>
    </div>
  );
}

export default App;
