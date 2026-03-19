import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Building2 } from "lucide-react";
import { suppliersApi } from "../api/suppliers";
import { ComplianceBadge } from "../components/StatusBadge";
import { usePermissions } from "../hooks/usePermissions";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel, FieldGroup } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
    InputGroup,
    InputGroupAddon,
    InputGroupInput,
} from "@/components/ui/input-group";
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
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Card } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";

function CreateSupplierDialog({ canCreateSupplier, trigger }) {
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
            qc.invalidateQueries({ queryKey: ["suppliers"] });
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
            <DialogTrigger asChild>
                {trigger || (
                    <Button disabled={!canCreateSupplier}>
                        <Plus size={16} /> Nouveau fournisseur
                    </Button>
                )}
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
                <form
                    onSubmit={(e) => {
                        e.preventDefault();
                        mutation.mutate(form);
                    }}
                >
                    <DialogHeader className="mb-4">
                        <DialogTitle>Nouveau fournisseur</DialogTitle>
                        <DialogDescription>
                            Renseignez les informations pour créer un
                            fournisseur.
                        </DialogDescription>
                    </DialogHeader>

                    <FieldGroup>
                        <Field>
                            <FieldLabel htmlFor="supplier-name">
                                Raison sociale <span className="text-destructive">*</span>
                            </FieldLabel>
                            <Input
                                id="supplier-name"
                                name="name"
                                value={form.name}
                                onChange={set("name")}
                                placeholder="ACME SAS"
                                required
                            />
                        </Field>
                        <Field>
                            <FieldLabel htmlFor="supplier-siret">
                                SIRET <span className="text-destructive">*</span>
                            </FieldLabel>
                            <Input
                                id="supplier-siret"
                                name="siret"
                                value={form.siret}
                                onChange={set("siret")}
                                placeholder="73282932000074"
                                pattern="\d{14}"
                                title="14 chiffres"
                                maxLength={14}
                                required
                            />
                        </Field>
                        <div className="grid grid-cols-2 gap-3">
                            <Field>
                                <FieldLabel htmlFor="supplier-email">
                                    Email <span className="text-destructive">*</span>
                                </FieldLabel>
                                <Input
                                    id="supplier-email"
                                    name="email"
                                    type="email"
                                    value={form.email}
                                    onChange={set("email")}
                                    placeholder="contact@acme.com"
                                    required
                                />
                            </Field>
                            <Field>
                                <FieldLabel htmlFor="supplier-phone">
                                    Téléphone
                                </FieldLabel>
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
                            <FieldLabel htmlFor="supplier-address">
                                Adresse
                            </FieldLabel>
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
                            {mutation.isPending ? <Spinner size={15} /> : null}
                            Créer
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
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
        <div className="p-8 max-w-6xl mx-auto">
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
                {canCreateSupplier && !isLoading && suppliers.length > 0 && (
                    <CreateSupplierDialog
                        canCreateSupplier={canCreateSupplier}
                    />
                )}
            </div>

            <Field className="max-w-xs w-full mb-6">
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

            <Card className="shadow-none p-0">
                <Table className="px-6 text-sm">
                    <TableHeader>
                        <TableRow>
                            <TableHead>Fournisseur</TableHead>
                            <TableHead className="hidden md:table-cell">
                                Contact
                            </TableHead>
                            <TableHead>Documents</TableHead>
                            <TableHead>Conformité</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {isLoading ? (
                            Array.from({ length: 5 }).map((_, i) => (
                                <TableRow key={i} className="animate-pulse">
                                    {Array.from({ length: 4 }).map((_, j) => (
                                        <TableCell key={j}>
                                            <div className="h-4 bg-background rounded-sm w-3/4" />
                                        </TableCell>
                                    ))}
                                </TableRow>
                            ))
                        ) : suppliers.length === 0 ? (
                            <Empty>
                                <EmptyHeader>
                                    <EmptyMedia variant="icon">
                                        <Building2 />
                                    </EmptyMedia>
                                    <EmptyTitle>
                                        Aucun fournisseur trouvé
                                    </EmptyTitle>
                                    <EmptyDescription>
                                        Vous n'avez pas encore créé de
                                        fournisseur.
                                    </EmptyDescription>
                                    <EmptyContent className="flex-row justify-center gap-2">
                                        {canCreateSupplier && (
                                            <CreateSupplierDialog
                                                canCreateSupplier={
                                                    canCreateSupplier
                                                }
                                                trigger={
                                                    <Button>
                                                        <Plus size={16} />
                                                        Ajouter un fournisseur
                                                    </Button>
                                                }
                                            />
                                        )}
                                    </EmptyContent>
                                </EmptyHeader>
                            </Empty>
                        ) : (
                            suppliers.map((s) => (
                                <TableRow key={s.supplier_id}>
                                    <TableCell className="max-w-xs">
                                        <div className="flex items-center gap-3 min-w-0">
                                            <div className="w-9 h-9 bg-primary-100 rounded-lg flex items-center justify-center shrink-0">
                                                <Building2
                                                    size={18}
                                                    className="text-primary-600"
                                                />
                                            </div>
                                            <div className="min-w-0">
                                                <Link
                                                    to={`/suppliers/${s.supplier_id}`}
                                                    className="text-gray-800 hover:text-primary-600 font-medium truncate block"
                                                >
                                                    {s.name}
                                                </Link>
                                                <p className="text-xs text-gray-400 truncate">
                                                    {s.siret
                                                        ? `SIRET : ${s.siret}`
                                                        : "SIRET non renseigné"}
                                                </p>
                                            </div>
                                        </div>
                                    </TableCell>
                                    <TableCell className="hidden md:table-cell text-gray-500">
                                        {s.email || s.phone || "—"}
                                    </TableCell>
                                    <TableCell>
                                        <span className="text-xs text-gray-400">
                                            {s.document_count} doc
                                            {s.document_count > 1 ? "s" : ""}
                                        </span>
                                    </TableCell>
                                    <TableCell>
                                        <ComplianceBadge
                                            status={s.compliance_status}
                                        />
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </Card>
        </div>
    );
}
