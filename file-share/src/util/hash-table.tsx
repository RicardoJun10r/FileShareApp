import { No } from "./no";

export class HashTable<T extends Object>{

    private size: number;

    private vetor: (No<T> | undefined)[];

    public constructor(){
        this.size = 5;
        this.vetor = new Array(this.size);
    }

    put(valor: T): void {
        let index = this.hashFunction(valor);
        let elemento: No<T> | undefined = this.vetor[index];

        while(elemento != null){
            if(elemento.getDado() === valor) break;
            elemento = elemento.getProximo();
        }

        if(elemento == null){
            elemento = new No<T>(valor);

            elemento.setProximo(this.vetor[index]);
        }
    }

    get(valor: T): any {
        let index = this.hashFunction(valor);
        
        let elemento: No<T> | undefined = this.vetor[index];

        while(elemento != null){
            if(elemento.getDado() === valor) return elemento;
            elemento = elemento.getProximo();
        }

        return null;
    }

    private hashFunction(valor: T): number{
        return Number.parseInt(valor.toString()) % this.size;
    }

}