import { ColumnDef } from '@tanstack/react-table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';
import { Button } from '../ui/button';
import { MoreHorizontal } from 'lucide-react';
import { Arquivo } from '@/shared/obj-interface';
import pako from 'pako';

const base64ToUint8Array = (base64: string): Uint8Array => {
  const binaryString = atob(base64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes;
};

const handleDownload = (base64Data: string, fileName: string) => {
  const compressedContent = base64ToUint8Array(base64Data);

  const decompressedContent = pako.inflate(compressedContent);

  const blob = new Blob([decompressedContent], { type: 'application/octet-stream' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

export const columns_file: ColumnDef<Arquivo>[] = [
  {
    header: 'Horario',
    accessorKey: 'horario',
    cell: ({ getValue }) => {
      const date = new Date(getValue() as string);
      return date.toLocaleTimeString();
    },
  },
  {
    header: 'Nome',
    accessorKey: 'nome',
  },
  {
    header: 'Tipo',
    accessorKey: 'tipo',
  },
  {
    header: 'Tamanho',
    accessorKey: 'tamanho',
    cell: ({ getValue }) => `${getValue()} bytes`,
  },
  {
    header: 'Contador',
    cell: ({ row }) => {
      const contador = row.original.contador;
      const minutos = Math.floor(contador / 60);
      const segundos = contador % 60;
      return <span>{`${minutos}:${segundos.toString().padStart(2, '0')}`}</span>;
    },
  },
  {
    id: 'actions',
    cell: ({ row }) => {
      const arquivo = row.original;

      return (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant='ghost' className='h-8 w-8 p-0'>
              <span className='sr-only'>Abrir menu</span>
              <MoreHorizontal className='h-4 w-4' />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuGroup>
              <DropdownMenuLabel>Ações</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => handleDownload(arquivo.arquivo, arquivo.nome)}>
                Download
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      );
    },
  },
];
