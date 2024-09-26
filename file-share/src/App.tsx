import { useState, useEffect } from 'react'
import { columns_file } from './components/tables/column-table'
import { DataTable } from './components/tables/data-table'
import { Input } from './components/ui/input'
import { Label } from './components/ui/label'
import { HashTable } from './util/hash-table'
import { Arquivo } from './shared/obj-interface'
import { Button } from './components/ui/button'

function App() {

  const [file, setFile] = useState<File | null>(null);

  const hashTable = new HashTable<number, Arquivo>();

  const handleOnChangeFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setFile(file);
    }
  }

  const upload = () => {

    if (file) {
      let novo_arquvio: Arquivo = {
        horario: new Date(),
        nome: file?.name,
        tamanho: file?.size,
        tipo: file?.type,
        arquivo: file
      }

      hashTable.put(novo_arquvio.horario.getTime(), novo_arquvio)

      console.log('baixou')

      hashTable.print()
    }

  }


  useEffect(() => { }, [file])


  return (
    <div className='h-screen w-screen justify-center flex items-center'>
      <header className='top-0 fixed'>
      </header>
      <main>
        <div>
          <div className="grid w-full max-w-sm items-center gap-1.5">
            <Label htmlFor="arquivo">Arquivo</Label>
            <Input onChange={handleOnChangeFile} id="arquivo" type="file" />
            <Button onClick={upload}>Upload</Button>
          </div>
          <div className='w-screen'>
            <DataTable columns={columns_file} data={[]} />
          </div>
        </div>
      </main>
      <footer className='bottom-0 fixed'>
        {file && (
          <div>
            <p>{file.name}</p>
            <p>{file.type}</p>
            <p>{file.size}</p>
          </div>
        )}
      </footer>
    </div>
  )
}

export default App
