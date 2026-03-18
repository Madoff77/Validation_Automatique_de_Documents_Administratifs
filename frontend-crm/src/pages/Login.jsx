import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import {
    Eye,
    EyeOff,
    Loader2,
    ScanText,
    FileText,
    Receipt,
    ArrowRight,
    FileCheck,
    FileClock,
    FileSearch,
} from "lucide-react";

import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";

const floatingCards = [
    {
        icon: FileCheck,
        label: "Conformité validée",
        sub: "KBIS · SIRET · URSSAF",
        style: {
            top: "22%",
            left: "8%",
            "--rot": "-4deg",
            "--dur": "11s",
            "--delay": "0s",
        },
    },
    {
        icon: ScanText,
        label: "OCR adaptatif",
        sub: "Tesseract 5 · pdfplumber",
        style: {
            top: "38%",
            left: "58%",
            "--rot": "3deg",
            "--dur": "13s",
            "--delay": "1.5s",
        },
    },
    {
        icon: FileClock,
        label: "Pipeline Airflow",
        sub: "11 documents traités",
        style: {
            top: "55%",
            left: "8%",
            "--rot": "-2deg",
            "--dur": "9s",
            "--delay": "0.8s",
        },
    },
    {
        icon: FileSearch,
        label: "Extraction ML",
        sub: "TF-IDF · Random Forest",
        style: {
            top: "68%",
            left: "70%",
            "--rot": "5deg",
            "--dur": "14s",
            "--delay": "2s",
        },
    },
    {
        icon: Receipt,
        label: "FACTURE #2024-089",
        sub: "Montant HT · TVA · IBAN",
        style: {
            top: "16%",
            left: "48%",
            "--rot": "2deg",
            "--dur": "12s",
            "--delay": "0.4s",
        },
    },
    {
        icon: FileText,
        label: "Kbis — BTP Solutions",
        sub: "Validé · < 90 jours",
        style: {
            top: "43%",
            left: "25%",
            "--rot": "-3deg",
            "--dur": "10s",
            "--delay": "1.2s",
        },
    },
];

function GridOverlay() {
    return (
        <svg
            className="absolute inset-0 w-full h-full opacity-[0.06] pointer-events-none"
            xmlns="http://www.w3.org/2000/svg"
        >
            <defs>
                <pattern
                    id="grid"
                    width="48"
                    height="48"
                    patternUnits="userSpaceOnUse"
                >
                    <path
                        d="M 48 0 L 0 0 0 48"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="0.8"
                    />
                </pattern>
            </defs>
            <rect
                width="100%"
                height="100%"
                fill="url(#grid)"
                className="text-primary"
            />
        </svg>
    );
}

function BlobsOverlay() {
    return (
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
            <div
                className="absolute rounded-full blur-[90px] opacity-25"
                style={{
                    width: 340,
                    height: 340,
                    top: "-80px",
                    left: "-60px",
                    background: "var(--primary)",
                }}
            />
            <div
                className="absolute rounded-full blur-[120px] opacity-15"
                style={{
                    width: 280,
                    height: 280,
                    bottom: "60px",
                    right: "-40px",
                    background: "var(--chart-2)",
                }}
            />
            <div
                className="absolute rounded-full blur-[80px] opacity-10"
                style={{
                    width: 200,
                    height: 200,
                    top: "45%",
                    left: "35%",
                    background: "var(--chart-3)",
                }}
            />
        </div>
    );
}

function FloatingCard({ icon: Icon, label, sub, style }) {
    return (
        <div
            className="bubble-float absolute flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg border border-border/60 backdrop-blur-sm"
            style={{
                ...style,
                background: "color-mix(in oklch, var(--card) 80%, transparent)",
                minWidth: 200,
            }}
        >
            <div
                className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                style={{
                    background:
                        "color-mix(in oklch, var(--primary) 12%, transparent)",
                }}
            >
                <Icon size={15} style={{ color: "var(--primary)" }} />
            </div>
            <div>
                <div
                    className="text-xs font-semibold leading-tight"
                    style={{ color: "var(--foreground)" }}
                >
                    {label}
                </div>
                <div
                    className="text-[10px] leading-tight mt-0.5"
                    style={{ color: "var(--muted-foreground)" }}
                >
                    {sub}
                </div>
            </div>
        </div>
    );
}

function ConnectorLines() {
    return (
        <svg
            className="absolute inset-0 w-full h-full pointer-events-none opacity-20"
            xmlns="http://www.w3.org/2000/svg"
        >
            <line
                x1="18%"
                y1="26%"
                x2="34%"
                y2="45%"
                stroke="var(--primary)"
                strokeWidth="1"
                strokeDasharray="4 6"
            />
            <line
                x1="34%"
                y1="45%"
                x2="62%"
                y2="42%"
                stroke="var(--primary)"
                strokeWidth="1"
                strokeDasharray="4 6"
            />
            <line
                x1="62%"
                y1="22%"
                x2="62%"
                y2="42%"
                stroke="var(--primary)"
                strokeWidth="1"
                strokeDasharray="4 6"
            />
            <line
                x1="18%"
                y1="58%"
                x2="34%"
                y2="45%"
                stroke="var(--primary)"
                strokeWidth="1"
                strokeDasharray="4 6"
            />
            <line
                x1="75%"
                y1="70%"
                x2="34%"
                y2="45%"
                stroke="var(--primary)"
                strokeWidth="1"
                strokeDasharray="4 6"
            />
            {[
                ["18%", "26%"],
                ["34%", "45%"],
                ["62%", "42%"],
                ["62%", "22%"],
                ["18%", "58%"],
                ["75%", "70%"],
            ].map(([cx, cy], i) => (
                <circle
                    key={i}
                    cx={cx}
                    cy={cy}
                    r="3"
                    fill="var(--primary)"
                    opacity="0.6"
                />
            ))}
        </svg>
    );
}

export default function Login() {
    const { login } = useAuth();
    const navigate = useNavigate();
    const [form, setForm] = useState({ username: "", password: "" });
    const [showPwd, setShowPwd] = useState(false);
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            await login(form.username, form.password);
            navigate("/dashboard");
        } catch (err) {
            toast.error(
                err.response?.data?.detail || "Identifiants incorrects",
            );
        } finally {
            setLoading(false);
        }
    };

    const fillDemo = (role) => {
        const creds = {
            admin: { username: "admin", password: "admin123" },
            operator: { username: "operator", password: "operator123" },
            viewer: { username: "viewer", password: "viewer123" },
        };
        setForm(creds[role]);
    };

    return (
        <div className="min-h-screen grid grid-cols-2 overflow-hidden max-[820px]:grid-cols-1">
            <div
                className="relative overflow-hidden flex flex-col justify-end p-14 max-[820px]:hidden"
                style={{ background: "var(--secondary)" }}
            >
                <GridOverlay />
                <BlobsOverlay />
                <ConnectorLines />
                {floatingCards.map((card) => (
                    <FloatingCard key={card.label} {...card} />
                ))}
                <div className="absolute top-10 left-14 z-10 flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center shadow-md shrink-0 bg-primary">
                        <ScanText size={18} color="white" />
                    </div>
                    <div>
                        <div className="font-prata font-semibold text-base leading-tight">
                            DocPlatform
                        </div>
                        <div className="text-xs tracking-tighter text-muted-foreground">
                            CRM
                        </div>
                    </div>
                </div>
                <div className="relative z-10">
                    <h2 className="font-prata leading-[1.3] mb-3.5 font-semibold text-5xl">
                        Vos documents,
                        <br />
                        <em className="not-italic text-muted-foreground">
                            compris
                        </em>{" "}
                        en
                        <br />
                        quelques secondes.
                    </h2>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                        Extraction intelligente · Classification automatique ·
                        Conformité garantie
                    </p>
                </div>
            </div>
            <div className="flex items-center justify-center px-10 py-12 relative">
                <div className="grid gap-7 form-in w-full max-w-100">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <div className="header-dot w-1.5 h-1.5 rounded-full bg-primary" />
                            <span className="text-xs text-muted-foreground uppercase tracking-widest font-medium">
                                CRM
                            </span>
                        </div>
                        <h1 className="font-prata text-[2rem] font-semibold leading-snug mb-1.5">
                            Connexion
                        </h1>
                        <p className="text-xs text-muted-foreground leading-normal">
                            Entrez vos identifiants pour accéder à votre espace
                        </p>
                    </div>
                    <form onSubmit={handleSubmit}>
                        <FieldGroup>
                            <Field>
                                <FieldLabel htmlFor="username">
                                    Nom d'utilisateur
                                </FieldLabel>
                                <Input
                                    id="username"
                                    type="text"
                                    placeholder="ex : martin.dupont"
                                    value={form.username}
                                    onChange={(e) =>
                                        setForm({
                                            ...form,
                                            username: e.target.value,
                                        })
                                    }
                                    required
                                    autoFocus
                                    autoComplete="username"
                                />
                            </Field>
                            <Field>
                                <FieldLabel htmlFor="password">
                                    Mot de passe
                                </FieldLabel>
                                <div className="relative">
                                    <Input
                                        id="password"
                                        type={showPwd ? "text" : "password"}
                                        placeholder="••••••••"
                                        value={form.password}
                                        onChange={(e) =>
                                            setForm({
                                                ...form,
                                                password: e.target.value,
                                            })
                                        }
                                        autoComplete="current-password"
                                        required
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPwd(!showPwd)}
                                        className="absolute right-4 top-1/2 -translate-y-1/2 bg-transparent text-primary border-none cursor-pointer p-0 flex items-center transition-colors duration-150"
                                    >
                                        {showPwd ? (
                                            <EyeOff size={15} />
                                        ) : (
                                            <Eye size={15} />
                                        )}
                                    </button>
                                </div>
                            </Field>
                            <Field orientation="horizontal">
                                <Button
                                    type="submit"
                                    size="lg"
                                    disabled={loading}
                                    className="w-full"
                                >
                                    {loading ? (
                                        <>
                                            <Loader2
                                                size={15}
                                                className="spin"
                                            />
                                            Connexion…
                                        </>
                                    ) : (
                                        <>
                                            <span>Se connecter</span>
                                            <ArrowRight size={15} />
                                        </>
                                    )}
                                </Button>
                            </Field>
                        </FieldGroup>
                    </form>
                    <div className="flex gap-2">
                        {["admin", "operator", "viewer"].map((role) => (
                            <Button
                                key={role}
                                variant="outline"
                                size="sm"
                                className="flex-1 text-xs capitalize"
                                onClick={() => fillDemo(role)}
                            >
                                {role}
                            </Button>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
