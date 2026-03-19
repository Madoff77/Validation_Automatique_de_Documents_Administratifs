import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Building2, ChevronRight, Loader2 } from "lucide-react";
import { suppliersApi } from "../api/suppliers";
import { ComplianceBadge } from "../components/StatusBadge";
import { usePermissions } from "../hooks/usePermissions";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
    InputGroup,
    InputGroupAddon,
    InputGroupInput,
} from "@/components/ui/input-group";
import { Label } from "@/components/ui/label";
import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";

function CreateSupplierDialog({ canCreateSupplier }) {
    const qc = useQueryClient();
    const navigate = useNavigate();
    const [open, setOpen] = useState(false);
    const [form, setForm] = useState({
        name: "",
        siret: "",
        email: "",
        phone: "",
        address: "",
    });

    const mutation = useMutation({
        mutationFn: suppliersApi.create,
        onSuccess: (data) => {
            qc.invalidateQueries(["suppliers"]);
            toast.success(`Fournisseur ${data.name} créé`);
            navigate(`/suppliers/${data.supplier_id}`);
            setOpen(false);
        },
        onError: (e) =>
            toast.error(
                e.response?.data?.detail || "Erreur lors de la création",
            ),
    });

    const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <form
                onSubmit={(e) => {
                    e.preventDefault();
                    mutation.mutate(form);
                }}
            >
                <DialogTrigger asChild>
                    <Button disabled={!canCreateSupplier}>
                        <Plus size={16} /> Nouveau fournisseur
                    </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>Nouveau fournisseur</DialogTitle>
                        <DialogDescription>
                            Renseignez les informations pour créer un
                            fournisseur.
                        </DialogDescription>
                    </DialogHeader>
                    <FieldGroup>
                        <Field>
                            <Label htmlFor="supplier-name">
                                Raison sociale *
                            </Label>
                            <Input
                                id="supplier-name"
                                name="name"
                                value={form.name}
                                onChange={set("name")}
                                required
                                placeholder="ACME SAS"
                            />
                        </Field>
                        <Field>
                            <Label htmlFor="supplier-siret">SIRET</Label>
                            <Input
                                id="supplier-siret"
                                name="siret"
                                value={form.siret}
                                onChange={set("siret")}
                                placeholder="73282932000074"
                                pattern="\d{14}"
                                title="14 chiffres"
                            />
                        </Field>
                        <div className="grid grid-cols-2 gap-3">
                            <Field>
                                <Label htmlFor="supplier-email">Email</Label>
                                <Input
                                    id="supplier-email"
                                    name="email"
                                    type="email"
                                    value={form.email}
                                    onChange={set("email")}
                                    placeholder="contact@acme.com"
                                />
                            </Field>
                            <Field>
                                <Label htmlFor="supplier-phone">
                                    Téléphone
                                </Label>
                                <Input
                                    id="supplier-phone"
                                    name="phone"
                                    value={form.phone}
                                    onChange={set("phone")}
                                    placeholder="01 23 45 67 89"
                                />
                            </Field>
                        </div>
                        <Field>
                            <Label htmlFor="supplier-address">Adresse</Label>
                            <Input
                                id="supplier-address"
                                name="address"
                                value={form.address}
                                onChange={set("address")}
                                placeholder="123 Rue de Exemple, 75000 Paris"
                            />
                        </Field>
                    </FieldGroup>
                    <DialogFooter className="pt-2">
                        <DialogClose asChild>
                            <Button type="button" variant="outline">
                                Annuler
                            </Button>
                        </DialogClose>
                        <Button type="submit" disabled={mutation.isPending}>
                            {mutation.isPending ? (
                                <Loader2 size={15} className="animate-spin" />
                            ) : null}
                            Créer
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </form>
        </Dialog>
    );
}

export default function Suppliers() {
    const [search, setSearch] = useState("");
    const { canCreateSupplier } = usePermissions();

    const { data: suppliers = [], isLoading } = useQuery({
        queryKey: ["suppliers", search],
        queryFn: () => suppliersApi.list({ search: search || undefined }),
    });

    return (
        <div className="p-8 max-w-5xl mx-auto">
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="font-prata text-2xl font-bold text-gray-900">
                        Fournisseurs
                    </h1>
                    <p className="text-sm text-gray-500 mt-0.5">
                        {suppliers.length} fournisseur
                        {suppliers.length > 1 ? "s" : ""}
                    </p>
                </div>
                {canCreateSupplier && (
                    <CreateSupplierDialog
                        canCreateSupplier={canCreateSupplier}
                    />
                )}
            </div>
            <Field className="max-w-xs w-full">
                <InputGroup>
                    <InputGroupAddon>
                        <Search size={16} />
                    </InputGroupAddon>
                    <InputGroupInput
                        id="search"
                        placeholder="Rechercher par nom ou SIRET..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </InputGroup>
            </Field>
            <div className="card divide-y divide-gray-50">
                {isLoading ? (
                    Array.from({ length: 5 }).map((_, i) => (
                        <div
                            key={i}
                            className="flex items-center gap-4 px-6 py-4 animate-pulse"
                        >
                            <div className="w-10 h-10 bg-gray-200 rounded-lg" />
                            <div className="flex-1 space-y-2">
                                <div className="h-4 w-48 bg-gray-200 rounded" />
                                <div className="h-3 w-32 bg-gray-200 rounded" />
                            </div>
                        </div>
                    ))
                ) : suppliers.length === 0 ? (
                    <div className="px-6 py-16 text-center">
                        <Building2
                            size={40}
                            className="mx-auto text-gray-300 mb-3"
                        />
                        <p className="text-gray-500 text-sm">
                            Aucun fournisseur trouvé
                        </p>
                    </div>
                ) : (
                    suppliers.map((s) => (
                        <Link
                            key={s.supplier_id}
                            to={`/suppliers/${s.supplier_id}`}
                            className="flex items-center gap-4 px-6 py-4 hover:bg-gray-50 transition-colors group"
                        >
                            <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center shrink-0">
                                <Building2
                                    size={20}
                                    className="text-primary-600"
                                />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="font-medium text-gray-900 truncate">
                                    {s.name}
                                </p>
                                <p className="text-sm text-gray-400">
                                    {s.siret
                                        ? `SIRET : ${s.siret}`
                                        : "SIRET non renseigné"}
                                    {s.email ? ` · ${s.email}` : ""}
                                </p>
                            </div>
                            <div className="flex items-center gap-3 shrink-0">
                                <span className="text-xs text-gray-400">
                                    {s.document_count} doc
                                    {s.document_count > 1 ? "s" : ""}
                                </span>
                                <ComplianceBadge status={s.compliance_status} />
                                <ChevronRight
                                    size={16}
                                    className="text-gray-300 group-hover:text-gray-500 transition-colors"
                                />
                            </div>
                        </Link>
                    ))
                )}
            </div>
        </div>
    );
}
