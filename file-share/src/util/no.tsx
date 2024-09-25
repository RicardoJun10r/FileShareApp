export class No<T extends Object>{

    private dado: T | undefined;

    private proximo: No<T> | undefined;

    public constructor(valor: T){
        this.dado = valor;
        this.proximo = undefined;
    }

    getDado(): T | undefined{
        return this.dado;
    }

    getProximo(): No<T> | undefined{
        return this.proximo;
    }

    setProximo(proximo: (No<T> | undefined)){
        this.proximo = proximo;
    }

}
