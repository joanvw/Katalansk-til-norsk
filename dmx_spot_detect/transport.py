"""Transportlag for RDM.

``detect_fixtures`` bryr seg ikke om *hvordan* RDM-pakkene sendes – bare at
den kan (1) oppdage hvilke UID-er som finnes på linjen, og (2) hente en
parameter (GET) fra en gitt UID. Dette gjør at logikken kan testes med en
``MockRDMTransport`` uten maskinvare, mens ``OlaRDMTransport`` snakker med
ekte grensesnitt via Open Lighting Architecture (OLA).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .rdm_types import UID


@runtime_checkable
class RDMTransport(Protocol):
    """Minimumsgrensesnittet detektoren trenger fra en RDM-forbindelse."""

    def discover(self) -> list[UID]:
        """Kjør RDM-oppdaging og returner UID-ene som svarer på linjen."""
        ...

    def rdm_get(self, uid: UID, pid: int) -> bytes | None:
        """Send en RDM GET til ``uid`` for ``pid``.

        Returnerer parameterdataene (uten RDM-header), eller ``None`` hvis
        enheten ikke svarte / ikke støtter parameteren.
        """
        ...


class MockRDMTransport:
    """Transport i minnet – nyttig for testing og demo uten maskinvare.

    Fylles med et oppslag ``{UID: {pid: bytes}}``. Manglende PID-er
    simulerer en enhet som ikke støtter parameteren (returnerer ``None``).
    """

    def __init__(self, devices: dict[UID, dict[int, bytes]]):
        self._devices = devices

    def discover(self) -> list[UID]:
        return sorted(self._devices.keys())

    def rdm_get(self, uid: UID, pid: int) -> bytes | None:
        return self._devices.get(uid, {}).get(pid)


class OlaRDMTransport:
    """RDM over et ekte grensesnitt via Open Lighting Architecture.

    Krever at OLA (``olad``) kjører og at Python-bindingene (``ola``-pakken)
    er installert. Fungerer med alle RDM-grensesnitt OLA støtter – Enttec
    DMX USB Pro, DMXKing, uDMX-noder, Art-Net/sACN-gateways osv.

    Bevisst tynn: den kjører oppdaging og rå GET-er, mens all tolkning av
    svaret gjøres i ``rdm_types``/``detector`` slik at logikken kan testes
    uten maskinvare.
    """

    def __init__(self, universe: int = 1, discovery_timeout: float = 10.0):
        self.universe = universe
        self.discovery_timeout = discovery_timeout

    # OLA sitt Python-API er callback-basert; vi pakker det inn i synkrone
    # kall med en egen ClientWrapper per operasjon.
    def discover(self) -> list[UID]:
        from ola.ClientWrapper import ClientWrapper  # importeres lazy

        wrapper = ClientWrapper()
        client = wrapper.Client()
        result: list[UID] = []

        def _cb(status, uids):
            if status.Succeeded():
                result.extend(UID(u.manufacturer_id, u.device_id) for u in uids)
            wrapper.Stop()

        # full=True gjør en fullstendig binærsøk-oppdaging på linjen.
        client.RunRDMDiscovery(self.universe, True, _cb)
        wrapper.Run()
        return sorted(result)

    def rdm_get(self, uid: UID, pid: int) -> bytes | None:
        from ola.ClientWrapper import ClientWrapper
        from ola.OlaClient import OlaClient
        from ola.UID import UID as OlaUID

        wrapper = ClientWrapper()
        client = wrapper.Client()
        payload: dict[str, bytes | None] = {"data": None}

        def _cb(response, data, unpacked):
            if (
                response.response_code == OlaClient.RDM_COMPLETED_OK
                and response.response_type == OlaClient.RDM_ACK
            ):
                payload["data"] = bytes(data)
            wrapper.Stop()

        client.RDMGet(
            self.universe,
            OlaUID(uid.manufacturer_id, uid.device_id),
            0,  # sub-device
            pid,
            _cb,
        )
        wrapper.Run()
        return payload["data"]
