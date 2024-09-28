import { useState, useEffect } from 'react'
import { columns_file } from './components/tables/column-table'
import { DataTable } from './components/tables/data-table'
import { Input } from './components/ui/input'
import { Label } from './components/ui/label'
import { Arquivo } from './shared/obj-interface'
import { Button } from './components/ui/button'
import pako from 'pako'

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [cont, setCont] = useState(0);
  const [data, setData] = useState<Arquivo[]>([]);

  const handleOnChangeFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setFile(file);
    }
  };

  const upload = () => {
    if (file) {
      const reader = new FileReader();

      reader.onload = () => {
        const fileContent = new Uint8Array(reader.result as ArrayBuffer);
        const compressedContent = pako.deflate(fileContent);

        const compressedFile = new File([compressedContent], file.name, {
          type: file.type,
          lastModified: file.lastModified
        });

        let novo_arquvio: Arquivo = {
          horario: new Date(),
          nome: file.name,
          tamanho: file.size,
          tipo: file.type,
          arquivo: compressedFile,
          contador: 300
        };

        setCont(prevCont => prevCont + 1);

        setData(prevData => [...prevData, novo_arquvio]);

        const intervalId = setInterval(() => {
          setData(prevData => 
            prevData.map(item => {
              if (item.nome === novo_arquvio.nome) {
                if (item.contador > 0) {
                  return { ...item, contador: item.contador - 1 };
                } else {
                  setCont(prevCont => prevCont - 1);
                  clearInterval(intervalId);
                  return null;
                }
              }
              return item;
            }).filter(item => item !== null)
          );
        }, 1000);

        console.log('Arquivo carregado com sucesso');
      };

      reader.readAsArrayBuffer(file);
    }
  };

  useEffect(() => {}, [file]);

  return (
    <div className='h-screen w-screen justify-center flex items-center'>
      <header className='top-0 fixed bg-slate-500 w-full flex justify-between items-center px-4 py-2'>
        <h1 className="text-left">
          FileShare
        </h1>
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
          <div className='w-screen'>
            <DataTable columns={columns_file} data={data} />
          </div>
        </div>
      </main>
      <footer className='bottom-0 p-4 fixed flex justify-center bg-slate-400 w-full'>
        {file && (
          <div className='flex space-x-3'>
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
