"""Enkelt grafisk grensesnitt (tkinter – følger med Python på Windows/macOS)."""

from __future__ import annotations

import os
import queue
import threading
import traceback


def start() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    from .app import Valg, eksporter_alle
    from .eksport import parse_navnefil, parse_par, parse_tallsett as _tallsett
    from .sdkort import finn_sesjoner
    from .usb import finn_scenefiler, finn_xlive_kort, usb_disker

    rot = tk.Tk()
    rot.title("X-Live eksport – X32 / M32")
    rot.geometry("900x680")
    rot.minsize(700, 520)

    v_kort = tk.StringVar()
    v_ut = tk.StringVar(value=os.path.expanduser("~/X-Live eksport"))
    v_kilde = tk.StringVar(value="ingen")
    v_scene = tk.StringVar()
    v_ip = tk.StringVar()
    v_bits = tk.StringVar(value="24")
    v_auto = tk.BooleanVar(value=True)
    v_stereo = tk.StringVar()
    v_mono = tk.StringVar()
    v_hopp = tk.StringVar()
    v_navn = tk.StringVar()
    v_stille = tk.BooleanVar(value=False)
    v_kopier = tk.BooleanVar(value=True)
    v_verifiser = tk.BooleanVar(value=False)
    sesjoner: list = []
    meldinger: queue.Queue = queue.Queue()

    ramme = ttk.Frame(rot, padding=12)
    ramme.pack(fill="both", expand=True)
    ramme.columnconfigure(1, weight=1)

    def mappevelger(var, tittel):
        def velg():
            d = filedialog.askdirectory(title=tittel)
            if d:
                var.set(d)
                if var is v_kort:
                    skann()
        return velg

    def filvelger(var, tittel, typer):
        def velg():
            f = filedialog.askopenfilename(title=tittel, filetypes=typer)
            if f:
                var.set(f)
        return velg

    rad = 0
    ttk.Label(ramme, text="SD-kort / mappe:").grid(row=rad, column=0, sticky="w")
    ttk.Entry(ramme, textvariable=v_kort).grid(row=rad, column=1, sticky="ew", padx=6)
    ttk.Button(ramme, text="Velg …", command=mappevelger(v_kort, "Velg SD-kortet")).grid(row=rad, column=2)
    ttk.Button(ramme, text="Skann", command=lambda: skann()).grid(row=rad, column=3, padx=(6, 0))
    rad += 1
    ttk.Button(ramme, text="Finn kort på USB (kortleser)", command=lambda: finn_usb()).grid(
        row=rad, column=1, sticky="w", padx=6, pady=(4, 0))

    rad += 1
    ttk.Label(ramme, text="Sesjoner (merk de du vil ha):").grid(row=rad, column=0, columnspan=4, sticky="w", pady=(10, 2))
    rad += 1
    liste = tk.Listbox(ramme, selectmode="extended", height=8, font=("TkFixedFont", 10))
    liste.grid(row=rad, column=0, columnspan=4, sticky="nsew")
    ramme.rowconfigure(rad, weight=1)

    rad += 1
    ttk.Label(ramme, text="Målmappe:").grid(row=rad, column=0, sticky="w", pady=(10, 0))
    ttk.Entry(ramme, textvariable=v_ut).grid(row=rad, column=1, sticky="ew", padx=6, pady=(10, 0))
    ttk.Button(ramme, text="Velg …", command=mappevelger(v_ut, "Velg målmappe")).grid(row=rad, column=2, pady=(10, 0))

    rad += 1
    kilde = ttk.LabelFrame(ramme, text="Kanalnavn, EQ, kompressor, gate og FX hentes fra", padding=8)
    kilde.grid(row=rad, column=0, columnspan=4, sticky="ew", pady=(10, 0))
    kilde.columnconfigure(1, weight=1)
    ttk.Radiobutton(kilde, text="Ingen (bare «Spor 01» …)", variable=v_kilde, value="ingen").grid(row=0, column=0, sticky="w")
    ttk.Radiobutton(kilde, text="Scenefil (.scn):", variable=v_kilde, value="scene").grid(row=1, column=0, sticky="w")
    ttk.Entry(kilde, textvariable=v_scene).grid(row=1, column=1, sticky="ew", padx=6)
    ttk.Button(kilde, text="Velg …", command=filvelger(v_scene, "Velg scenefil",
               [("X32/M32-scene", "*.scn"), ("Alle filer", "*")])).grid(row=1, column=2)
    ttk.Radiobutton(kilde, text="Miksebord på nett (IP):", variable=v_kilde, value="ip").grid(row=2, column=0, sticky="w")
    ttk.Entry(kilde, textvariable=v_ip, width=18).grid(row=2, column=1, sticky="w", padx=6)

    rad += 1
    opp = ttk.LabelFrame(ramme, text="Valg", padding=8)
    opp.grid(row=rad, column=0, columnspan=4, sticky="ew", pady=(10, 0))
    ttk.Label(opp, text="Bitdybde:").grid(row=0, column=0, sticky="w")
    ttk.Combobox(opp, textvariable=v_bits, values=["24", "32", "16", "samme"], width=7,
                 state="readonly").grid(row=0, column=1, sticky="w", padx=6)
    ttk.Checkbutton(opp, text="Stereo av linkede kanaler", variable=v_auto).grid(row=0, column=2, sticky="w", padx=12)
    ttk.Checkbutton(opp, text="Fjern helt stille spor", variable=v_stille).grid(row=0, column=3, sticky="w")
    ttk.Label(opp, text="Ekstra stereopar:").grid(row=1, column=0, sticky="w", pady=(6, 0))
    ttk.Entry(opp, textvariable=v_stereo, width=16).grid(row=1, column=1, sticky="w", padx=6, pady=(6, 0))
    ttk.Label(opp, text="Alltid mono:").grid(row=1, column=2, sticky="e", pady=(6, 0))
    ttk.Entry(opp, textvariable=v_mono, width=16).grid(row=1, column=3, sticky="w", padx=6, pady=(6, 0))
    ttk.Label(opp, text="Hopp over spor:").grid(row=2, column=0, sticky="w", pady=(6, 0))
    ttk.Entry(opp, textvariable=v_hopp, width=16).grid(row=2, column=1, sticky="w", padx=6, pady=(6, 0))
    ttk.Label(opp, text="Navnefil (spor;navn):").grid(row=2, column=2, sticky="e", pady=(6, 0))
    ttk.Entry(opp, textvariable=v_navn, width=24).grid(row=2, column=3, sticky="w", padx=6, pady=(6, 0))
    ttk.Button(opp, text="…", width=3, command=filvelger(v_navn, "Velg navnefil",
               [("Tekst/CSV", "*.txt *.csv"), ("Alle filer", "*")])).grid(row=2, column=4, pady=(6, 0))
    ttk.Checkbutton(opp, text="Kopier råfiler fra kortet først (sikkerhetskopi)",
                    variable=v_kopier).grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))
    ttk.Checkbutton(opp, text="Verifiser kopien", variable=v_verifiser).grid(
        row=3, column=3, sticky="w", pady=(6, 0))

    rad += 1
    fremdrift = ttk.Progressbar(ramme, maximum=1000)
    fremdrift.grid(row=rad, column=0, columnspan=3, sticky="ew", pady=(10, 0))
    knapp = ttk.Button(ramme, text="Eksporter", command=lambda: kjor())
    knapp.grid(row=rad, column=3, pady=(10, 0))

    rad += 1
    loggfelt = tk.Text(ramme, height=10, font=("TkFixedFont", 9))
    loggfelt.grid(row=rad, column=0, columnspan=4, sticky="nsew", pady=(8, 0))
    ramme.rowconfigure(rad, weight=1)

    def logg(tekst: str) -> None:
        meldinger.put(("logg", tekst))

    def vis(nye) -> None:
        sesjoner.clear()
        liste.delete(0, "end")
        sesjoner.extend(nye)
        for s in sesjoner:
            liste.insert("end", s.beskrivelse())
        liste.select_set(0, "end")
        logg(f"Fant {len(sesjoner)} sesjon(er).")

    def skann() -> None:
        if v_kort.get():
            vis(finn_sesjoner(v_kort.get()))

    def finn_usb(stille: bool = False) -> None:
        disker = usb_disker()
        kort = finn_xlive_kort(disker)
        if kort:
            for disk, ss in kort:
                logg(f"X-Live-kort på USB: {disk} – {len(ss)} sesjon(er)")
            v_kort.set(kort[0][0].sti if len(kort) == 1 else "")
            vis([s for _, ss in kort for s in ss])
        elif not stille:
            messagebox.showinfo("X-Live", "Fant ikke noe X-Live-kort på USB.\n\n"
                                "Ta SD-kortet ut av X-Live-kortet og sett det i en USB-kortleser. "
                                "(X-Live-kortets egen USB-port er et lydkort og viser ikke SD-kortet.)")
        scener = finn_scenefiler(disker)
        if scener and not v_scene.get():
            v_scene.set(scener[0])
            v_kilde.set("scene")
            logg(f"Scenefil funnet på USB: {scener[0]}")

    def kjor() -> None:
        valgte = [sesjoner[i] for i in liste.curselection()]
        if not valgte:
            messagebox.showwarning("X-Live", "Velg minst én sesjon.")
            return
        try:
            valg = Valg(
                utmappe=v_ut.get(),
                scenefil=v_scene.get() if v_kilde.get() == "scene" and v_scene.get() else None,
                miksebord_ip=v_ip.get().strip() if v_kilde.get() == "ip" and v_ip.get().strip() else None,
                bits=v_bits.get() if v_bits.get() == "samme" else int(v_bits.get()),
                auto_stereo=v_auto.get(), stereopar=parse_par(v_stereo.get()),
                monospor=_tallsett(v_mono.get()), hopp_over=_tallsett(v_hopp.get()),
                navn=parse_navnefil(v_navn.get()) if v_navn.get() else {},
                fjern_stille=v_stille.get(), kopier_raa=v_kopier.get(),
                verifiser=v_verifiser.get())
        except (ValueError, OSError) as e:
            messagebox.showerror("X-Live", str(e))
            return
        knapp.state(["disabled"])

        def arbeid():
            try:
                eksporter_alle(valgte, valg, logg=logg,
                               fremdrift=lambda a, t: meldinger.put(("fremdrift", a)))
                meldinger.put(("ferdig", valg.utmappe))
            except Exception as e:  # noqa: BLE001 – vis alle feil i GUI-et
                logg(traceback.format_exc())
                meldinger.put(("feil", str(e)))

        threading.Thread(target=arbeid, daemon=True).start()

    def pump() -> None:
        try:
            while True:
                type_, verdi = meldinger.get_nowait()
                if type_ == "logg":
                    loggfelt.insert("end", verdi + "\n")
                    loggfelt.see("end")
                elif type_ == "fremdrift":
                    fremdrift["value"] = int(verdi * 1000)
                elif type_ == "ferdig":
                    knapp.state(["!disabled"])
                    messagebox.showinfo("X-Live", f"Ferdig! Filene ligger i\n{verdi}")
                elif type_ == "feil":
                    knapp.state(["!disabled"])
                    messagebox.showerror("X-Live", verdi)
        except queue.Empty:
            pass
        rot.after(100, pump)

    pump()
    rot.after(300, lambda: finn_usb(stille=True))
    rot.mainloop()
