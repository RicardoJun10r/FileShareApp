export interface Arquivo {
    horario: Date
    nome: string | undefined
    tipo: string | undefined
    tamanho: number | undefined
    arquivo: File | null
}