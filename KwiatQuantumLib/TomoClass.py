from .TomoFunctions import *
import numpy as np

class Tomography():

    ######################
    '''Public Variables'''
    ######################

    # conf['NQubits']: >= 1, it will take a much longer time for more qubits.
    # conf['NDetectors']: 1 or 2
    # conf['ctalk']: [[C0->0, C0->1],[C1->0, C1->1]]
    # conf['UseDerivative']: 0 or 1
    # conf['Bellstate']: 0 or 1
    # conf['DoErrorEstimation']: 0 or 1
    # conf['DoDriftCorrection'] = 'no' or 'yes'
    # conf['Window']: 0 or array like, demension = 1
    # conf['Efficiency']: 0 or array like, demension = 1
    # conf['Beta']: 0 to 0.5, depending on purity of state and total number of measurements.
    #Default self.conf
    conf = {'NQubits': 2,
            'NDetectors': 1,
            'Crosstalk': np.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]),
            'UseDerivative': 0,
            'DoErrorEstimation': 0,
            'DoDriftCorrection': 'no',
            'DoAccidentalCorrection' : 1,
            'Window': 0,
            'Efficiency': [1, 1, 1, 1],
            'RhoStart': [],
            'IntensityMap': [[1]],
            'StateDimention': 0,
            'StateDimention': 0,
            'Beta': 0,
            'QuditSizes': [2, 2]

    }
    # tomo_input: array like, demension = 2.
    #
    # For n detectors:
    # tomo_input[:, 0]: times
    # tomo_input[:, np.arange(1, n_qubit+1)]: singles
    # input[:, n_qubit+1]: coincidences
    # input[:, np.arange(n_qubit+2, 3*n_qubit+2)]: measurements
    #
    # For 2n detectors:
    # tomo_input[:, 0]: times
    # tomo_input[:, np.arange(1, 2*n_qubit+1)]: singles
    # input[:, np.arange(2*n_qubit+1, 2**n_qubit+2*n_qubit+1)]: coincidences
    # input[:, np.arange(2**n_qubit+2*n_qubit+1, 2**n_qubit+4*n_qubit+1)]: measurements
    tomo_input = 0

    err_n = 0
    err_functions = ['']

    ##################
    '''Constructors'''
    ##################

    #Default Constructor
    def __init__(self):
        pass

    #Sets a specific self.conf setting
    def setConfSetting(self,setting,val):
        self.conf[setting] = val

    #inport self.conf.txt file. Input argument is string of filename
    def importConf(self,conftxt):
        conf = self.conf
        exec(compile(open(conftxt, "rb").read(), conftxt, 'exec'))
    #inport data.txt file. Input argument is string of filename
    def importData(self,datatxt):
        exec(compile(open(datatxt, "rb").read(), datatxt, 'exec'))
        return self.state_tomography(locals().get('tomo_input'), locals().get('intensity'))
    #inport pythoneval.txt file. Input argument is string of filename
    #Performs Tomography
    def importPythonEval(self,pythonevaltxt):
        conf = self.conf

        exec(compile(open(pythonevaltxt, "rb").read(), pythonevaltxt, 'exec'))
        return self.state_tomography(locals().get('tomo_input'), locals().get('intensity'))

    ##########################
    '''Tomography Functions'''
    ##########################

    def state_tomography(self,raw_counts, intensities):
        rho0 = self.conf['RhoStart']
        ndet = self.conf['NDetectors']
        nBits = self.conf['NQubits']
        if nBits == 1:
            if ndet == 2:
                [data, m1, m2, acc] = self.filter_data_2det_1bit(raw_counts, intensities)
                # 2ndet still need to check with data
            elif ndet == 1:
                [data, m1, m2, acc] = self.filter_data_1det_1bit(raw_counts)
        else:
            if ndet == 2:
                [data, m1, m2, acc] = self.filter_data_2det_2bit(raw_counts, intensities)
                # 2ndet still need to check with data
            elif ndet == 1:
                [data, m1, m2, acc] = self.filter_data_1det_2bit(raw_counts)
            else:
                print("n_det is neither 1 or 2")
                data = 0
                m1 = 0
                m2 = 0
                acc = 0

        if not rho0:
            rho0 = self.linear_tomography(data, m2)[0]

        [rhog, intensities, fvalp] = self.maximum_likelihood_tomography(rho0, data, m1, acc)
        return [rhog, intensities, fvalp]


    def maximum_likelihood_tomography(self,rho0, data, m, acc):
        rho0 = make_positive(rho0)
        rho0 /= np.trace(rho0)
        init_intensity = np.mean(data) * (rho0.shape[0])
        t0 = density2t(rho0)
        n_t = len(t0)

        # t_to_density(t0)
        t0 = t0 + 0.0001
        t0 = t0 * np.sqrt(init_intensity)

        # this [[1]] is not good
        intmap = self.conf['IntensityMap']
        n_int = np.array(np.shape(intmap))[1] - 1
        t0 = np.concatenate((t0, np.ones(n_int)), axis=0)
        # options
        useder = self.conf['UseDerivative']
        # ndet = self.conf['NDetectors', 1)
        if type(useder) is str:
            useder = useder is 'yes'

        data = np.real(data)
        data = data.flatten()

        intmap = self.conf['IntensityMap']
        sz = self.conf['StateDimention']
        bet = self.conf['Beta']
        # n_data = np.shape(data)[0]

        n_int = np.array(np.shape(intmap))[1] - 1
        if sz > 0:
            nt = sz ** 2
        else:
            nt = len(t0) - n_int
            # sz = np.sqrt(nt)

        prediction = np.zeros(m.shape[2]) + 0j
        fvalp = 0

        if useder:
            [aa, bb] = self.initialize_fitness_global(m)
            t = leastsq(self.maxlike_fitness, np.real(t0), args=(data, acc, m, intmap, n_int, nt, prediction, aa, bb),
                        Dfun=self.maxlike_fitness_der_d)[0]
        else:
            if bet == 0:
                t = leastsq(self.maxlike_fitness, np.real(t0), args=(data, acc, m, intmap, n_int, nt, prediction))[0]
                fvalp = np.sum(self.maxlike_fitness(t, data, acc, m, intmap, n_int, nt, prediction) ** 2)
            else:
                t = \
                leastsq(self.maxlike_fitness_hedged, np.real(t0), args=(data, acc, m, intmap, n_int, nt, prediction, bet))[0]
                fvalp = np.sum(self.maxlike_fitness_hedged(t, data, acc, m, intmap, n_int, nt, prediction, bet) ** 2)

        # base_intensity = np.sum((t[range(n_t)])**2)
        # t_matrix(t[range(n_t)])
        matrix = t_to_density(t[0:n_t])
        intensities = np.trace(matrix)
        rhog = matrix / intensities
        intensities = np.float64(np.real(intensities))

        return [rhog, intensities, fvalp]

    def maxlike_fitness(self, t, data, accidentals, m, intmap, n_int, nt, prediction, aa=0, bb=0):

        tm = t_matrix(t[0:nt])
        # do not change
        rhog = np.dot(tm.conj().transpose(), tm)

        if n_int > 0:
            rel_intensity = np.dot(intmap, [1, t[nt:len(t)]])
        else:
            rel_intensity = np.ones(m.shape[2])

        for j in range(len(prediction)):
            prediction[j] = rel_intensity[j] * np.real(np.trace(np.dot(m[:, :, j], rhog))) + accidentals[j]
            prediction[j] = np.max([prediction[j], 0.01])
        val = (prediction - data) / np.sqrt(prediction)

        val = np.float64(np.real(val))

        return val

    def maxlike_fitness_hedged(self,t, data, accidentals, m, intmap, n_int, nt, prediction, bet):

        tm = t_matrix(t[0:nt])
        # do not change
        rhog = np.dot(tm.conj().transpose(), tm)

        if n_int > 0:
            rel_intensity = np.dot(intmap, [1, t[nt:len(t)]])
        else:
            rel_intensity = np.ones(m.shape[2])

        for j in range(len(prediction)):
            prediction[j] = rel_intensity[j] * np.real(np.trace(np.dot(m[:, :, j], rhog))) + accidentals[j]
            prediction[j] = np.max([prediction[j], 0.01])

        hedge = np.repeat(np.real((bet * np.log(np.linalg.det(np.mat(rhog)))) / len(prediction)), len(prediction))
        val = np.sqrt(np.real((((prediction - data) ** 2) / (2 * prediction)) - hedge) + 1000)

        val = np.float64(np.real(val))

        return val

    def maxlike_fitness_der_d(self,t, data, accidentals, m, intmap, n_int, nt, prediction, aa, bb):

        tm = t_matrix(t[0:nt])
        # do not change
        rhog = np.dot(tm.conj().transpose(), tm)

        # I ignore something here using nargin and nargout, kinda difficult in python, seems like A and B checkpoint

        if n_int > 0:
            rel_intensity = np.dot(intmap, [1, t[nt:len(t)]])
        else:
            rel_intensity = np.ones(m.shape[2])

        for j in range(len(prediction)):
            prediction[j] = rel_intensity[j] * np.real(np.trace(np.dot(m[:, :, j], rhog))) + accidentals[j]
            prediction[j] = np.max([prediction[j], 0.01])

        jacob = 0
        jacob1 = np.zeros([len(data), nt]) + 0j
        for j in range(len(data)):
            for k in range(nt):
                tmp = np.dot(aa[j][k].conj().transpose(), tm) + np.dot(tm.conj().transpose(), bb[j][k])
                jacob1[j][k] = rel_intensity[j] * np.trace(tmp) / np.sqrt(prediction[j])
                jacob1[j][k] = jacob1[j][k] * (1 - 0.5 + 0.5 * data[j] / prediction[j])

        if n_int > 0:
            tmp1 = ((prediction - accidentals) / np.sqrt(prediction)) * (1 - 0.5 + 0.5 * data / prediction)
            tmp2 = np.outer(tmp1, 1 / t[np.arange(nt, len(t))].transpose())
            jacob2 = np.dot(intmap, np.vstack((np.zeros(10), np.identity(10)))) * tmp2
            jacob = np.hstack((jacob1, jacob2))
        else:
            jacob = jacob1
        jacob = np.array(np.float64(np.real(jacob)))

        return jacob

    def linear_tomography(self,data, measurements, m_set=()):
        if m_set == ():
            m_set = independent_set(measurements)
        if np.isscalar(m_set):
            n = len(data)
            linear_measurements = measurements
            linear_data = data

        else:
            n = np.int(np.sum(m_set))
            linear_measurements = measurements[(np.rot90(m_set == 1.0)[0])]
            linear_data = data[(np.rot90(m_set == 1.0)[0])]

        linear_rhog = np.zeros([measurements.shape[1], measurements.shape[1]])

        b = b_matrix(linear_measurements)
        b_inv = np.linalg.inv(b)

        m = np.zeros([measurements.shape[1], measurements.shape[1], n]) + 0j
        for j in range(n):
            m[:, :, j] = m_matrix(j, linear_measurements, b_inv)
            linear_rhog = linear_rhog + linear_data[j] * m[:, :, j]

        intensities = np.trace(linear_rhog)
        rhog = linear_rhog / intensities

        return [rhog, intensities]

    def filter_data_1det_1bit(self,raw_counts):
        n_qubit = self.conf['NQubits']
        n = map(int, np.ones(n_qubit) * 2)
        # qudit_sizes = self.conf['QuditSizes', n)
        qudit_sizes = 2
        self.conf['StateDimension'] = np.prod(qudit_sizes)
        window = self.conf['Window']
        n_singles = 1
        n_measurements = len(raw_counts)

        t = raw_counts[:, 0]
        sings = raw_counts[:, np.arange(n_singles) + 1]
        coinc = raw_counts[:, n_singles + 1]
        measurements = raw_counts[:, np.arange(n_singles + 2, len(raw_counts[0]))]

        acc = np.prod(sings, axis=1) * (window * 1e-9 / t) ** (n_singles - 1)

        m2 = np.zeros([n_measurements, 2])
        m1 = np.zeros([np.prod(qudit_sizes), np.prod(qudit_sizes), n_measurements])
        m2 = m2 + 0j
        m1 = m1 + 0j
        for j in range(n_measurements):
            psi = 1
            offset = 0
            for k in range(n_singles):
                m_length = qudit_sizes
                psi_k = measurements[j, np.arange(offset, offset + m_length)]
                psi = tensor_product_2(psi, psi_k)
                offset = offset + m_length
            m2[j, :] = psi
            m1[:, :, j] = np.outer(psi, psi.conj().transpose())

        return [coinc, m1, m2, acc]

    def filter_data_1det_2bit(self,raw_counts):
        n_qubit = self.conf['NQubits']
        n = map(int, np.ones(n_qubit)*2)
        #qudit_sizes = self.conf['QuditSizes', n)
        qudit_sizes = self.conf['QuditSizes']
        self.conf['StateDimension'] = np.prod(qudit_sizes)
        window = self.conf['Window']
        n_singles = len(qudit_sizes)
        n_measurements = len(raw_counts)

        t = raw_counts[:, 0]
        sings = raw_counts[:, np.arange(n_singles)+1]
        coinc = raw_counts[:, n_singles+1]
        measurements = raw_counts[:, np.arange(n_singles+2, len(raw_counts[0]))]

        acc = np.prod(sings, axis=1)*(window*1e-9/t)**(n_singles-1)

        m2 = np.zeros([n_measurements, np.prod(qudit_sizes)])
        m1 = np.zeros([np.prod(qudit_sizes), np.prod(qudit_sizes), n_measurements])
        m2 = m2+0j
        m1 = m1+0j
        for j in range(n_measurements):
            psi = 1
            offset = 0
            for k in range(n_singles):
                m_length = qudit_sizes[k]
                psi_k = measurements[j, np.arange(offset, offset+m_length)]
                psi = tensor_product_2(psi, psi_k)
                offset = offset+m_length
            m2[j, :] = psi
            m1[:, :, j] = np.outer(psi, psi.conj().transpose())

        return [coinc, m1, m2, acc]

    def filter_data_2det_1bit(self,raw_counts, intensities):
        if not np.isscalar(intensities):
            self.conf['DoDriftCorrection'] = 0
        nbits = self.conf['NQubits']
        do_drift_corr = self.conf['DoDriftCorrection']
        self.conf['StateDimension'] = 2**nbits

        n_singles = 2*nbits
        n_coinc = 2**nbits

        t = raw_counts[:, 0]
        sings = raw_counts[:, np.arange(n_singles)+1]
        coinc = raw_counts[:, np.arange(n_singles+1, n_singles+n_coinc+1)]
        settings = raw_counts[:, np.arange(n_singles+n_coinc+1, len(raw_counts[0]))]

        acc = np.zeros(np.shape(coinc))

        window = self.conf['Window']
        if not np.isscalar(window):
            if any(window) > 0:
                for j in range(n_coinc):
                    idx = multiloop_index(j, 2*np.ones(nbits))
                    idx = idx + np.arange(0, n_singles-1, 2) - 1
                    idx = idx.astype(int)
                    acc[:, j] = np.prod(np.real(sings[:, idx]), axis=1) * (window[j]*1e-9/np.real(t))**(nbits-1)

        if do_drift_corr:
            intensity_map = np.dot(np.eye(raw_counts.shape[0]), np.ones(n_coinc))
            z = np.zeros(np.prod(coinc.shape))
            self.conf['intensityMap'] = np.concatenate(z, intensity_map)

        eff = self.conf['Efficiency']

        ctalk = self.conf['Crosstalk']
        if np.ndim(ctalk) < 3:
            crosstalk = ctalk
        else:
            crosstalk = ctalk
            for j in range(ctalk.shape[2]):
                crosstalk[j] = ctalk[:, :, j]

        if (ctalk == []):
            big_crosstalk = np.eye(2**nbits)
        else:
            big_crosstalk = crosstalk[:]

        big_crosstalk = big_crosstalk * np.outer(eff, np.ones(n_coinc))

        m = np.zeros([2**nbits, 2**nbits, np.prod(coinc.shape)])+0j
        m2 = np.zeros([np.prod(coinc.shape), 2**nbits])+0j
        for j in range(coinc.shape[0]):
            m_twiddle = np.zeros([2**nbits, 2**nbits, 2**nbits])+0j
            u = 1
            for k in range(nbits):
                alpha = settings[j][2*k]
                beta = settings[j][2*k+1]

                psi_k = np.array([alpha, beta])
                psip_k = np.array([np.conj(beta), np.conj(-alpha)])
                u_k = np.outer((np.array([1, 0])), psi_k) + np.outer((np.array([0, 1])), psip_k)
                u = tensor_product_2(u, u_k)
            for k in range(2**nbits):
                m_twiddle[k, :, :] = np.outer(u[:, k].conj().transpose(), u[:, k])
                m2[j*n_coinc+k, :] = u[:, k].conj().transpose()
            for k in range(2**nbits):
                for l in range(2**nbits):
                    m[:, :, j*(2**nbits)+k] = m[:, :, j*(2**nbits)+k] + m_twiddle[l, :, :]*big_crosstalk[k, l]
        m1 = m

        data = coinc.reshape((np.prod(coinc.shape), 1))
        acc = acc.reshape((np.prod(acc.shape), 1))
        return [data, m1, m2, acc]

    def filter_data_2det_2bit(self,raw_counts, intensities):
        if not np.isscalar(intensities):
            self.conf['DoDriftCorrection'] = 0
        nbits = self.conf['NQubits']
        do_drift_corr = self.conf['DoDriftCorrection']
        self.conf['StateDimension'] = 2**nbits

        n_singles = 2*nbits
        n_coinc = 2**nbits

        t = raw_counts[:, 0]
        sings = raw_counts[:, np.arange(n_singles)+1]
        coinc = raw_counts[:, np.arange(n_singles+1, n_singles+n_coinc+1)]
        settings = raw_counts[:, np.arange(n_singles+n_coinc+1, len(raw_counts[0]))]

        acc = np.zeros(np.shape(coinc))

        window = self.conf['Window']
        if not np.isscalar(window):
            if any(window) > 0:
                for j in range(n_coinc):
                    idx = multiloop_index(j, 2*np.ones(nbits))
                    idx = idx + np.arange(0, n_singles-1, 2) - 1
                    idx = idx.astype(int)
                    acc[:, j] = np.prod(np.real(sings[:, idx]), axis=1) * (window[j]*1e-9/np.real(t))**(nbits-1)

        if do_drift_corr:
            intensity_map = np.dot(np.eye(raw_counts.shape[0]), np.ones(n_coinc))
            z = np.zeros(np.prod(coinc.shape))
            self.conf['intensityMap'] = np.concatenate(z, intensity_map)

        eff = self.conf['Efficiency']

        ctalk = self.conf['Crosstalk']
        if np.ndim(ctalk) < 3:
            crosstalk = ctalk
        else:
            crosstalk = ctalk
            for j in range(ctalk.shape[2]):
                crosstalk[j] = ctalk[:, :, j]

        if (ctalk == []):
            big_crosstalk = np.eye(2**nbits)
        else:
            big_crosstalk = crosstalk[:]

        big_crosstalk = big_crosstalk * np.outer(eff, np.ones(n_coinc))

        m = np.zeros([2**nbits, 2**nbits, np.prod(coinc.shape)])+0j
        m2 = np.zeros([np.prod(coinc.shape), 2**nbits])+0j
        for j in range(coinc.shape[0]):
            m_twiddle = np.zeros([2**nbits, 2**nbits, 2**nbits])+0j
            u = 1
            for k in range(nbits):
                alpha = settings[j][2*k]
                beta = settings[j][2*k+1]

                psi_k = np.array([alpha, beta])
                psip_k = np.array([np.conj(beta), np.conj(-alpha)])
                u_k = np.outer((np.array([1, 0])), psi_k) + np.outer((np.array([0, 1])), psip_k)
                u = tensor_product_2(u, u_k)
            for k in range(2**nbits):
                m_twiddle[k, :, :] = np.outer(u[:, k].conj().transpose(), u[:, k])
                m2[j*n_coinc+k, :] = u[:, k].conj().transpose()
            for k in range(2**nbits):
                for l in range(2**nbits):
                    m[:, :, j*(2**nbits)+k] = m[:, :, j*(2**nbits)+k] + m_twiddle[l, :, :]*big_crosstalk[k, l]
        m1 = m

        data = coinc.reshape((np.prod(coinc.shape), 1))
        acc = acc.reshape((np.prod(acc.shape), 1))
        return [data, m1, m2, acc]

    def initialize_fitness_global(self, m):
        num_t = m.shape[0] ** 2
        num_m = m.shape[2]
        # M_size = np.shape(M)[0]

        tm = np.zeros([num_t, 4, 4]) + 0j

        for j in range(num_t):
            tm[j] = t_matrix(one_in(j, num_t))

        aa = np.zeros([num_m, num_t, 4, 4]) + 0j
        bb = aa
        for j in range(num_m):
            for k in range(num_t):
                # Should use a sparse matrix here to make it easy.
                aa[j][k] = np.dot(m[:, :, j], tm[k].conj().transpose())
                bb[j][k] = np.dot(tm[k], m[:, :, j])

        return [aa, bb]

    #####################
    '''ERROR FUNCTIONS'''
    #####################

    def tomography_error(self, rho0, rhop):
        if (self.err_n == 0):
            self.err_n = 2
        n_fun = len(self.err_functions)
        data = np.zeros([self.err_n, n_fun])
        fid = np.zeros(self.err_n)
        for j in range(self.err_n):
            fid[j] = fidelity(rho0, rhop[j, :, :])
            for k in range(n_fun):
                data[j, k] = self.fevel(self.err_functions[k], rhop[j, :, :])

        errors = np.zeros(n_fun)
        means = np.zeros(n_fun)

        for k in range(n_fun):
            errors[k] = np.std(data[:, k])
            means[k] = np.mean(data[:, k])
        mean_f = np.mean(fid)
        err_f = np.std(fid)

        return [means, errors, mean_f, err_f]

    def error_n(self):
        if self.conf['DoErrorEstimation'] > 100:
            return 100
        else:
            return self.conf['DoErrorEstimation']

    def fevel(self,funcname, *args):
        return eval(funcname)(*args)

    def tomography_error_states_generator(self, intensities, n=30):
        ndet = self.conf['NDetectors']
        nbits = self.conf['NQubits']
        acc = self.conf['DoAccidentalCorrection']
        rhop = np.zeros([n, 2 ** nbits, 2 ** nbits]) + 0j
        length = len(self.tomo_input[:, 0])
        if ndet == 1:
            time = np.reshape(self.tomo_input[:, 0], (length, 1))
            meas = self.tomo_input[:, np.arange(nbits + 2, len(self.tomo_input[0, :]))]
            for j in range(n):
                test_data = np.zeros([length, nbits + 1])
                if acc:
                    kk = range(nbits + 1)
                else:
                    kk = np.array([nbits])
                for k in kk:
                    for l in range(length):
                        test_data[l, k] = np.random.poisson(np.real(self.tomo_input[l, k + 1]))

                test_data = np.concatenate((time, test_data, meas), axis=1)

                rhop[j, :, :] = self.state_tomography(test_data, intensities)[0]

        elif ndet == 2:
            time = np.reshape(self.tomo_input[:, 0], (length, 1))
            meas = self.tomo_input[:, np.arange(nbits + 2 ** nbits + 1, len(self.tomo_input[0, :]))]
            for j in range(n):
                test_data = np.zeros([length, nbits + 2 ** nbits])
                if acc:
                    kk = range(nbits + 2 ** nbits)
                else:
                    kk = np.arange(nbits, nbits + 2 ** nbits)
                for k in kk:
                    for l in range(length):
                        test_data[l, k] = np.random.poisson(np.real(self.tomo_input[l, k + 1]))

                test_data = np.concatenate((time, test_data, meas), axis=1)

                rhop[j, :, :] = self.state_tomography(test_data, intensities)[0]

        return rhop

    def getproperties(self,rho0, errfunc):
        return [self.fevel(errf, rho0) for errf in errfunc]

    def websitebellsettings(self,rhog, partsize_init, partsize, t):

        [s, arange, brange, aprange, bprange] = self.websitebellsettings_range_init(rhog, partsize_init)
        a = 0
        b = 0
        ap = 0
        bp = 0

        for j in range(t):
            [s, a, ap, b, bp, arange, brange, aprange, bprange] = \
                self.websitebellsettings_range(rhog, partsize, arange, brange, aprange, bprange)

        return [s, a, ap, b, bp]

    def websitebellsettings_range_init(self,rhog, partsize):
        sval = 0
        aval = 0
        apval = 0
        bval = 0
        bpval = 0

        for a in np.linspace(0, np.pi / 2, partsize):
            for ap in np.linspace(a, np.pi / 2, partsize):
                for b in np.linspace(0, np.pi / 2, partsize):
                    for bp in np.linspace(b, np.pi / 2, partsize):
                        npp = np.real(np.trace(np.dot(coinmat(a, b), rhog)))
                        nmm = np.real(np.trace(np.dot(coinmat(a + np.pi / 2, b + np.pi / 2), rhog)))
                        e_ab = 2 * (npp + nmm) - 1

                        npp = np.real(np.trace(np.dot(coinmat(ap, b), rhog)))
                        nmm = np.real(np.trace(np.dot(coinmat(ap + np.pi / 2, b + np.pi / 2), rhog)))
                        e_apb = 2 * (npp + nmm) - 1

                        npp = np.real(np.trace(np.dot(coinmat(a, bp), rhog)))
                        nmm = np.real(np.trace(np.dot(coinmat(a + np.pi / 2, bp + np.pi / 2), rhog)))
                        e_abp = 2 * (npp + nmm) - 1

                        npp = np.real(np.trace(np.dot(coinmat(ap, bp), rhog)))
                        nmm = np.real(np.trace(np.dot(coinmat(ap + np.pi / 2, bp + np.pi / 2), rhog)))
                        e_apbp = 2 * (npp + nmm) - 1

                        s = e_ab + e_abp + e_apb + e_apbp - 2 * np.min([e_ab, e_abp, e_apb, e_apbp])

                        if s > sval:
                            sval = s
                            aval = a
                            apval = ap
                            bval = b
                            bpval = bp

        arange_s = [np.max([aval - ((np.pi / 2) / partsize), 0]), np.min([aval + ((np.pi / 2) / partsize), np.pi / 2])]
        aprange_s = [np.max([apval - ((np.pi / 2) / partsize), 0]),
                     np.min([apval + ((np.pi / 2) / partsize), np.pi / 2])]
        brange_s = [np.max([bval - ((np.pi / 2) / partsize), 0]), np.min([bval + ((np.pi / 2) / partsize), np.pi / 2])]
        bprange_s = [np.max([bpval - ((np.pi / 2) / partsize), 0]),
                     np.min([bpval + ((np.pi / 2) / partsize), np.pi / 2])]

        return [sval, arange_s, brange_s, aprange_s, bprange_s]

    def tomography_error_bell(self,rhop, partsize_init, partsize, t, n):
        belldata = np.zeros([n, 5])

        for j in range(n):
            belldata[j, :] = self.websitebellsettings(rhop[j, :, :], partsize_init, partsize, t)

        bmeans = np.zeros(5)
        berrors = np.zeros(5)

        for m in range(5):
            berrors[m] = np.std(belldata[:, m])
            bmeans[m] = np.mean(belldata[:, m])

        return [berrors, bmeans]

