export interface Arquivo {
    horario: Date
    nome: string
    tipo: string
    tamanho: number
    arquivo: File | null
}