import numpy as np
import numba

from . import loadDefaultParams as dp


def timeIntegration(params):
    """Sets up the parameters for time integration

    :param params: Parameter dictionary of the model
    :type params: dict
    :return: Integrated activity variables of the model
    :rtype: (numpy.ndarray,)
    """

    dt = params["dt"]  # Time step for the Euler intergration (ms)
    duration = params["duration"]  # imulation duration (ms)
    RNGseed = params["seed"]  # seed for RNG

    # ------------------------------------------------------------------------
    # local parameters
    # See Papadopoulos et al., Relations between large-scale brain connectivity and effects of regional stimulation
    # depend on collective dynamical state, arXiv, 2020
    tau_exc = params["tau_exc"]  #
    tau_inh = params["tau_inh"]  #
    c_excexc = params["c_excexc"]  #
    c_excinh = params["c_excinh"]  #
    c_inhexc = params["c_inhexc"]  #
    c_inhinh = params["c_inhinh"]  #
    a_exc = params["a_exc"]  #
    a_inh = params["a_inh"]  #
    mu_exc = params["mu_exc"]  #
    mu_inh = params["mu_inh"]  #
    
    # adaptation parameters:
    tau_adap = params["tau_adap"]
    a_adap = params["a_adap"]
    a_a = params['a_a'] # adaptation gain
    mu_a = params['mu_a'] # adaptation threshold

    # external input parameters:
    # Parameter of the Ornstein-Uhlenbeck process for the external input(ms)
    tau_ou = params["tau_ou"]
    # Parameter of the Ornstein-Uhlenbeck (OU) process for the external input ( mV/ms/sqrt(ms) )
    sigma_ou = params["sigma_ou"]
    # Mean external excitatory input (OU process)
    exc_ou_mean = params["exc_ou_mean"]
    # Mean external inhibitory input (OU process)
    inh_ou_mean = params["inh_ou_mean"]

    # ------------------------------------------------------------------------
    # global coupling parameters

    # Connectivity matrix
    # Interareal relative coupling strengths (values between 0 and 1), Cmat(i,j) connection from jth to ith
    Cmat = params["Cmat"]
    N = len(Cmat)  # Number of nodes
    K_gl = params["K_gl"]  # global coupling strength
    # Interareal connection delay
    lengthMat = params["lengthMat"]
    signalV = params["signalV"]

    if N == 1:
        Dmat = np.zeros((N, N))
    else:
        # Interareal connection delays, Dmat(i,j) Connnection from jth node to ith (ms)
        Dmat = dp.computeDelayMatrix(lengthMat, signalV)
        Dmat[np.eye(len(Dmat)) == 1] = np.zeros(len(Dmat))
    Dmat_ndt = np.around(Dmat / dt).astype(int)  # delay matrix in multiples of dt
    params["Dmat_ndt"] = Dmat_ndt
    # ------------------------------------------------------------------------
    # Initialization
    # Floating point issue in np.arange() workaraound: use integers in np.arange()
    t = np.arange(1, round(duration, 6) / dt + 1) * dt  # Time variable (ms)

    sqrt_dt = np.sqrt(dt)

    max_global_delay = np.max(Dmat_ndt)
    startind = int(max_global_delay + 1)  # timestep to start integration at

    # noise variable
    exc_ou = params["exc_ou"]
    inh_ou = params["inh_ou"]

    exc_ext = params["exc_ext"]
    inh_ext = params["inh_ext"]

    # state variable arrays, have length of t + startind
    # they store initial conditions AND simulated data
    excs = np.zeros((N, startind + len(t)))
    inhs = np.zeros((N, startind + len(t)))
    
    # adaptation variable array
    adaps = np.zeros((N, startind + len(t)))
    

    # ------------------------------------------------------------------------
    # Set initial values
    # if initial values are just a Nx1 array
    if np.shape(params["exc_init"])[1] == 1:
        exc_init = np.dot(params["exc_init"], np.ones((1, startind)))
        inh_init = np.dot(params["inh_init"], np.ones((1, startind)))
        adap_init = np.dot(params["adap_init"], np.ones((1, startind)))
    # if initial values are a Nxt array
    else:
        exc_init = params["exc_init"][:, -startind:]
        inh_init = params["inh_init"][:, -startind:]
        adap_init = params["adap_init"][:, -startind:]

    # xsd = np.zeros((N,N))  # delayed activity
    exc_input_d = np.zeros(N)  # delayed input to exc
    inh_input_d = np.zeros(N)  # delayed input to inh (note used)

    np.random.seed(RNGseed)

    # Save the noise in the activity array to save memory
    excs[:, startind:] = np.random.standard_normal((N, len(t)))
    inhs[:, startind:] = np.random.standard_normal((N, len(t)))
    
    adaps[:, startind:] = np.random.standard_normal((N, len(t)))
    #save the initial condition in activity array at position of simulation start (startind)
    excs[:, :startind] = exc_init
    inhs[:, :startind] = inh_init
    
    adaps[:, :startind] = adap_init

    noise_exc = np.zeros((N,))
    noise_inh = np.zeros((N,))

    # ------------------------------------------------------------------------

    return timeIntegration_njit_elementwise(
        startind,
        t,
        dt,
        sqrt_dt,
        N,
        Cmat,
        K_gl,
        Dmat_ndt,
        excs,
        inhs,
        exc_input_d,
        inh_input_d,
        exc_ext,
        inh_ext,
        tau_exc,
        tau_inh,
        a_exc,
        a_inh,
        mu_exc,
        mu_inh,
        c_excexc,
        c_excinh,
        c_inhexc,
        c_inhinh,
        noise_exc,
        noise_inh,
        exc_ou,
        inh_ou,
        exc_ou_mean,
        inh_ou_mean,
        tau_ou,
        sigma_ou,
        adaps,
        a_adap,
        tau_adap,
        a_a,
        mu_a,
    )


@numba.njit
def timeIntegration_njit_elementwise(
    startind,
    t,
    dt,
    sqrt_dt,
    N,
    Cmat,
    K_gl,
    Dmat_ndt,
    excs,
    inhs,
    exc_input_d,
    inh_input_d,
    exc_ext,
    inh_ext,
    tau_exc,
    tau_inh,
    a_exc,
    a_inh,
    mu_exc,
    mu_inh,
    c_excexc,
    c_excinh,
    c_inhexc,
    c_inhinh,
    noise_exc,
    noise_inh,
    exc_ou,
    inh_ou,
    exc_ou_mean,
    inh_ou_mean,
    tau_ou,
    sigma_ou,
    adaps,
    a_adap,
    tau_adap,
    a_a,
    mu_a,
):
    ### integrate ODE system:

    def S_E(x):
        return 1.0 / (1.0 + np.exp(-a_exc * (x - mu_exc)))

    def S_I(x):
        return 1.0 / (1.0 + np.exp(-a_inh * (x - mu_inh)))
    
    def S_A(x):
        return 1.0 / (1.0 + np.exp(-a_a * (x - mu_a)))

    for i in range(startind, startind + len(t)):

        # loop through all the nodes
        for no in range(N):

            # To save memory, noise is saved in the activity array
            noise_exc[no] = excs[no, i]
            noise_inh[no] = inhs[no, i]

            # delayed input to each node
            exc_input_d[no] = 0

            for l in range(N):
                exc_input_d[no] += K_gl * Cmat[no, l] * (excs[l, i - Dmat_ndt[no, l] - 1])

            # Wilson-Cowan model with adaptation
            adap_rhs = (
                1
                / tau_adap
                * (
                    - adaps[no, i - 1]
                    + ( a_adap * S_A(excs[no, i - 1]) ) )
            )
                
            exc_rhs = (
                1
                / tau_exc
                * (
                    - excs[no, i - 1] + S_E( #ommiting the refractory period
                     c_excexc * excs[no, i - 1]  # input from within the excitatory population
                    - c_inhexc * inhs[no, i - 1]  # input from the inhibitory population
                    - adaps[no, i - 1]  # spike-frequency adaptation as negative feedback term
                    + exc_ext # external input
                    + exc_input_d[no]  # input from other nodes
                    + exc_ou[no] ) # ou noise
                )
            )
            inh_rhs = (
                1
                / tau_inh
                * (
                    - inhs[no, i - 1] + S_I( #ommitting refractory period
                     c_excinh * excs[no, i - 1]  # input from the excitatory population
                    - c_inhinh * inhs[no, i - 1]  # input from within the inhibitory population
                    + inh_ext   # external input
                    + inh_ou[no])  # ou noise
                )
            )

            # Euler integration
            excs[no, i] = excs[no, i - 1] + dt * exc_rhs
            inhs[no, i] = inhs[no, i - 1] + dt * inh_rhs
            adaps[no, i] = adaps[no, i - 1] + dt * adap_rhs
           
            

            # Ornstein-Uhlenbeck process
            exc_ou[no] = (
                exc_ou[no] + (exc_ou_mean - exc_ou[no]) * dt / tau_ou + sigma_ou * sqrt_dt * noise_exc[no]
            )  # mV/ms
            inh_ou[no] = (
                inh_ou[no] + (inh_ou_mean - inh_ou[no]) * dt / tau_ou + sigma_ou * sqrt_dt * noise_inh[no]
            )  # mV/ms
            

    return t, excs, inhs, adaps, exc_ou, inh_ou
