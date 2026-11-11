#!/bin/bash

. ./VERSION
if [ -f ./Dockerfile.build.custom ]; then
. ./Dockerfile.build.custom
fi

if [ -z "${OPTIMIZE}" ]; then
	OPTIMIZE=skip
fi

if [ "${OPTIMIZE}" == "skip" ]; then
	sudo docker build --force-rm --tag=$REPOSITORY:${VERSION} $@ .

elif [ "${OPTIMIZE}" == "full" ]; then
	sudo docker build --force-rm --tag=$REPOSITORY:${VERSION} $@ .
	if [ $? -ne 0 ]; then
		echo "build main container failed"
		exit 100
	fi

	sudo ./Dockerfile.build.optimized.sh $@

else
	INTERMEDIATE_IMAGE_NAME="$REPOSITORY:${VERSION}_intermediate"
	INTERMADIATEDOCKER=/tmp/Dockerfile-$$

	sudo docker build --force-rm --tag=${INTERMEDIATE_IMAGE_NAME} $@ .
	if [ $? -ne 0 ] ; then
		echo "build intermediate failed"
		exit 100
	fi

	cat > ${INTERMADIATEDOCKER} <<EOF
FROM ${INTERMEDIATE_IMAGE_NAME} AS exportsource

FROM scratch
COPY --from=exportsource / /
EOF

	############################## expose ports ##################################
	while read PORT; do
		if [ "$PORT" == "" ]; then
			continue
		fi

		echo "EXPOSE $PORT" >> ${INTERMADIATEDOCKER}
	done < <(sudo docker image inspect -f '{{range $port, $unk := .Config.ExposedPorts}}{{printf "%s\n" $port}}{{end}}' ${INTERMEDIATE_IMAGE_NAME})

	############################## enviroment ####################################
	while read ENV; do
		if [ "$ENV" == "" ]; then
			continue
		fi
		while IFS='=' read a b; do
			echo "ENV ${a}=\"${b}\"" >> ${INTERMADIATEDOCKER}
		done< <(echo $ENV)
	done < <(sudo docker image inspect -f '{{range $p, $env := .Config.Env}}{{printf "%s\n" $env}}{{end}}' ${INTERMEDIATE_IMAGE_NAME})

	########################### work dir ######################################
	while read WORKDIR; do
		if [ "$WORKDIR" == "" -o "$WORKDIR" = "/" ]; then
			continue
		fi
		echo "WORKDIR ${WORKDIR}" >> ${INTERMADIATEDOCKER}
	done < <(sudo docker image inspect -f '{{ .Config.WorkingDir }}' ${INTERMEDIATE_IMAGE_NAME})

	########################### entry point ######################################
	while read part; do
		if [ "$part" == "" ]; then
		  continue
		fi
		eparts+=("$part")
	done < <(sudo docker image inspect -f '{{range $p, $part := .Config.Entrypoint}}{{printf "%s\n" $part}}{{end}}' ${INTERMEDIATE_IMAGE_NAME})

	if [ ${#eparts[@]} -ne 0 ]; then
		ENTRYPOINT="["

		for part in "${eparts[@]}" ; do
			part=$(printf '%s' "$part" | sed -e 's/[\\"]/\\&/g')

			if [ "$ENTRYPOINT" == "[" ]; then
			  ENTRYPOINT="${ENTRYPOINT}\"$part\""
			else
			  ENTRYPOINT="${ENTRYPOINT}, \"$part\""
			fi
		done

		ENTRYPOINT="${ENTRYPOINT}]"
	fi
	if [ ! -z "$ENTRYPOINT" ]; then
		echo "ENTRYPOINT $ENTRYPOINT" >> ${INTERMADIATEDOCKER}
	fi

	sudo docker build --force-rm --tag=$REPOSITORY:${VERSION} -f ${INTERMADIATEDOCKER} $@ .
	rm ${INTERMADIATEDOCKER}

	sudo docker save -o ${REPOSITORY/\//-}-$VERSION.tar $REPOSITORY:$VERSION
	gzip -f  ${REPOSITORY/\//-}-$VERSION.tar
	chmod 0666 ./${REPOSITORY/\//-}-$VERSION.tar.gz
fi
