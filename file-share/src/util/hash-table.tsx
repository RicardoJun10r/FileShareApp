import { No } from "./no";

export class HashTable<K extends number, T extends Object>{

    private size: number;

    private vetor: (No<K, T> | undefined)[];

    public constructor(){
        this.size = 5;
        this.vetor = new Array(this.size);
    }

    print(): void {
        for (let index = 0; index < this.size; index++) {
            console.log(index + ": " + this.vetor[index]?.print());
        }
    }

    put(chave: K, valor: T): void {
        let index = this.hashFunction(chave);
        let elemento: No<K, T> | undefined = this.vetor[index];
    
        while (elemento != null) {
            if (elemento.getDado() === valor) return;
            elemento = elemento.getProximo();
        }
    
        const novoElemento = new No<K, T>(chave, valor);
    
        novoElemento.setProximo(this.vetor[index]);
    
        this.vetor[index] = novoElemento;
    }
    

    get(chave: K): any {
        let index = this.hashFunction(chave);
        
        let elemento: No<K, T> | undefined = this.vetor[index];

        while(elemento != null){
            if(elemento.getChave() === chave) return elemento;
            elemento = elemento.getProximo();
        }

        return null;
    }

    private hashFunction(valor: K): number{
        return Number.parseInt(valor.toString()) % this.size;
    }

}