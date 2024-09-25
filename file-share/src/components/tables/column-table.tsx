'use client'

import { ColumnDef } from '@tanstack/react-table';
import { Dialog, DialogTrigger } from '../ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '../ui/dropdown-menu';
import { Button } from '../ui/button';
import { MoreHorizontal } from 'lucide-react';

export const columns_file: ColumnDef<Object>[] = [
    {
        header: 'Horario',
        accessorKey: 'horario'
    },
    {
        header: 'Nome',
        accessorKey: 'nome'
    },
    {
        header: 'Tipo',
        accessorKey: 'tipo'
    },
    {
        header: 'Tamanho',
        accessorKey: 'tamanho'
    },
    {
        id: "actions",
        cell: ({ row }) => {
            return (
                <Dialog>
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" className="h-8 w-8 p-0">
                                <span className="sr-only">Abrir menu</span>
                                <MoreHorizontal className="h-4 w-4" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent>
                            <DropdownMenuGroup>
                                <DropdownMenuLabel>Ações</DropdownMenuLabel>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem>
                                    <DialogTrigger>
                                        Abrir
                                    </DialogTrigger>
                                </DropdownMenuItem>
                            </DropdownMenuGroup>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </Dialog>
            )
        }
    }
]
