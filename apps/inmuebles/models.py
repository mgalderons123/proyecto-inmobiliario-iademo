from datetime import date, timedelta

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.currencies import CURRENCY_CHOICES
from apps.core.storage import PrivateMediaStorage

from .fields import EncryptedField, normalizar_nombre


class Inquilino(models.Model):
    cuenta = models.ForeignKey(
        "users.Cuenta", on_delete=models.PROTECT, related_name="inquilinos"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perfiles_inquilino",
    )
    nombre = EncryptedField()
    nombre_busqueda = models.CharField(max_length=200, db_index=True, blank=True, default="")
    email = EncryptedField(blank=True, default="")
    telefono = EncryptedField(blank=True, default="")
    documento = EncryptedField(verbose_name="Documento (DNI/RUC/Cédula)", blank=True, default="")
    direccion = EncryptedField(blank=True, default="")
    notas = models.TextField(blank=True, default="")
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="inquilinos")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre_busqueda"]
        constraints = [
            models.UniqueConstraint(
                fields=["cuenta", "user"],
                condition=models.Q(user__isnull=False),
                name="unique_tenant_user_per_account",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.cuenta_id and self.creado_por_id:
            from apps.users.accounts import ensure_account_for_user

            self.cuenta = ensure_account_for_user(self.creado_por)
        self.nombre_busqueda = normalizar_nombre(self.nombre)
        super().save(*args, **kwargs)
        if self.user_id and self.cuenta_id:
            from apps.users.models import MembresiaCuenta

            MembresiaCuenta.objects.get_or_create(
                cuenta_id=self.cuenta_id,
                user_id=self.user_id,
                defaults={"rol": MembresiaCuenta.Roles.INQUILINO, "activa": True},
            )

    def __str__(self):
        return self.nombre


class Propietario(models.Model):
    cuenta = models.ForeignKey(
        "users.Cuenta", on_delete=models.PROTECT, related_name="propietarios"
    )
    nombre = EncryptedField()
    nombre_busqueda = models.CharField(max_length=200, db_index=True, blank=True, default="")
    email = EncryptedField(blank=True, default="")
    telefono = EncryptedField(blank=True, default="")
    documento = EncryptedField(verbose_name="Documento (DNI/RUC/Cédula)", blank=True, default="")
    direccion = EncryptedField(blank=True, default="")
    notas = models.TextField(blank=True, default="")
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="propietarios")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre_busqueda"]

    def save(self, *args, **kwargs):
        if not self.cuenta_id and self.creado_por_id:
            from apps.users.accounts import ensure_account_for_user

            self.cuenta = ensure_account_for_user(self.creado_por)
        self.nombre_busqueda = normalizar_nombre(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Inmueble(models.Model):
    cuenta = models.ForeignKey(
        "users.Cuenta", on_delete=models.PROTECT, related_name="inmuebles"
    )

    class Tipo(models.TextChoices):
        CASA = "casa", "Casa"
        DEPARTAMENTO = "dpto", "Departamento"
        TERRENO = "terreno", "Terreno"
        LOCAL = "local", "Local"
        OTRO = "otro", "Otro"

    class Estado(models.TextChoices):
        DISPONIBLE = "disponible", "Disponible"
        NO_DISPONIBLE = "no_disponible", "No disponible"
        ALQUILADO = "alquilado", "Alquilado"
        VENDIDO = "vendido", "Vendido"
        RESERVADO = "reservado", "Reservado"

    class TipoAlquiler(models.TextChoices):
        COMPLETA = "completa", "Completa"
        POR_HABITACIONES = "por_habitaciones", "Por habitaciones"
        POR_LOCAL = "por_local", "Por Local"

    titulo = models.CharField(max_length=200)
    direccion = models.TextField()
    descripcion = models.TextField(blank=True, default="")
    precio = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    moneda = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="USD")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.OTRO)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.DISPONIBLE)
    propietario = models.ForeignKey(Propietario, on_delete=models.SET_NULL, null=True, blank=True, related_name="inmuebles")
    superficie = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    habitaciones = models.PositiveIntegerField(null=True, blank=True)
    banos = models.PositiveIntegerField(null=True, blank=True)
    tipo_alquiler = models.CharField(
        max_length=20, choices=TipoAlquiler.choices, default=TipoAlquiler.COMPLETA,
        verbose_name="Tipo de alquiler",
    )
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    direccion_normalizada = models.TextField(blank=True, default="")
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="inmuebles")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.cuenta_id and self.creado_por_id:
            from apps.users.accounts import ensure_account_for_user

            self.cuenta = ensure_account_for_user(self.creado_por)
        if self.propietario_id and self.cuenta_id != self.propietario.cuenta_id:
            raise ValueError("El propietario y el inmueble deben pertenecer a la misma cuenta.")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.titulo


class FotoInmueble(models.Model):
    inmueble = models.ForeignKey(Inmueble, on_delete=models.CASCADE, related_name="fotos")
    imagen = models.ImageField(upload_to="inmuebles/%Y/%m/")
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden"]

    def __str__(self):
        return f"Foto {self.orden} de {self.inmueble.titulo}"


class Contrato(models.Model):
    class Tipo(models.TextChoices):
        ALQUILER = "alquiler", "Alquiler"
        VENTA = "venta", "Venta"
        AUTORIZACION_VENTA = "autorizacion_venta", "Autorización de Venta"

    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        FINALIZADO = "finalizado", "Finalizado"
        RESCINDIDO = "rescindido", "Rescindido"

    class FrecuenciaPago(models.TextChoices):
        DIARIO = "diario", "Diario"
        SEMANAL = "semanal", "Semanal"
        MENSUAL = "mensual", "Mensual"
        TRIMESTRAL = "trimestral", "Trimestral"
        SEMESTRAL = "semestral", "Semestral"
        ANUAL = "anual", "Anual"

    inmueble = models.ForeignKey(Inmueble, on_delete=models.CASCADE, related_name="contratos")
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.ACTIVO)
    inquilino = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="contratos")
    inquilino_registrado = models.ForeignKey(Inquilino, on_delete=models.SET_NULL, null=True, blank=True, related_name="contratos")
    inquilino_nombre = EncryptedField(blank=True, default="")
    inquilino_email = EncryptedField(blank=True, default="")
    inquilino_telefono = EncryptedField(blank=True, default="")
    frecuencia_pago = models.CharField(max_length=15, choices=FrecuenciaPago.choices, default=FrecuenciaPago.MENSUAL)
    duracion_anos = models.PositiveIntegerField(null=True, blank=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    moneda = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="USD")
    comision = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    garantia = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    fecha_finalizacion = models.DateField(null=True, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="contratos_creados")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.inmueble.titulo}"


class DocumentoContrato(models.Model):
    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name="documentos")
    archivo = models.BinaryField(editable=True)
    nombre = models.CharField(max_length=200, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveIntegerField(default=0)
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_subida"]

    def __str__(self):
        return self.nombre or f"Documento {self.pk}"


class Cuota(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        VENCIDO = "vencido", "Vencido"
        PAGADO = "pagado", "Pagado"
        PARCIAL = "parcial", "Parcial"

    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name="cuotas")
    numero = models.PositiveIntegerField()
    descripcion = models.CharField(max_length=200, blank=True, default="")
    fecha_vencimiento = models.DateField()
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    monto_multa = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha_pago = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["fecha_vencimiento", "numero"]
        unique_together = [("contrato", "numero")]

    @property
    def total(self):
        return self.monto + self.monto_multa

    @property
    def moneda(self):
        return self.contrato.moneda

    def __str__(self):
        return f"{self.descripcion or 'Cuota ' + str(self.numero)} - {self.contrato.inmueble.titulo}"


class Pago(models.Model):
    class Metodo(models.TextChoices):
        EFECTIVO = "efectivo", "Efectivo"
        TRANSFERENCIA = "transferencia", "Transferencia"
        CHEQUE = "cheque", "Cheque"
        DEPOSITO = "deposito", "Depósito"
        OTRO = "otro", "Otro"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        APROBADO = "aprobado", "Aprobado"
        RECHAZADO = "rechazado", "Rechazado"

    cuota = models.ForeignKey(Cuota, on_delete=models.CASCADE, related_name="pagos")
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    fecha_pago = models.DateField()
    metodo_pago = models.CharField(max_length=20, choices=Metodo.choices, default=Metodo.EFECTIVO)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE)
    archivo_comprobante = models.FileField(
        upload_to="comprobantes/%Y/%m/", storage=PrivateMediaStorage(), blank=True
    )
    comprobante = models.CharField(max_length=100, blank=True, default="")
    motivo_rechazo = models.TextField(blank=True, default="")
    observaciones = models.TextField(blank=True, default="")
    fecha_aprobacion = models.DateField(null=True, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="pagos")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_pago", "-created_at"]

    def __str__(self):
        return f"Pago {self.moneda} {self.monto} - {self.cuota} ({self.get_estado_display()})"

    @property
    def moneda(self):
        return self.cuota.contrato.moneda


class Recibo(models.Model):
    pago = models.OneToOneField(Pago, on_delete=models.CASCADE, related_name="recibo")
    codigo = models.CharField(max_length=20, unique=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Recibo {self.codigo}"
