export class No<K extends number, T extends Object>{

    private dado: T | undefined;

    private chave: K | undefined;

    private proximo: No<K, T> | undefined;

    public constructor(chave: K, valor: T){
        this.chave = chave;
        this.dado = valor;
        this.proximo = undefined;
    }

    getDado(): T | undefined{
        return this.dado;
    }

    getChave(): K | undefined {
        return this.chave;
    }

    getProximo(): No<K, T> | undefined{
        return this.proximo;
    }

    setProximo(proximo: (No<K, T> | undefined)){
        this.proximo = proximo;
    }

    print(): void{
        console.log("Dado: " + this.dado?.toString())
        console.log("Proximo: " + this.proximo?.print())
    }

}
